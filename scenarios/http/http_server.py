#! /usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

import argparse
import asyncio
import collections
import json
import pathlib
import ssl
import urllib.parse

import cbor_diag
import cbor2
import h2.config
import h2.connection
import h2.events
import psycopg2 as db
import psycopg2.errors as db_errors
import tornado


class H2Server(tornado.tcpserver.TCPServer):
    def __init__(self, database_uri, default_data_type, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.database_uri = database_uri
        self.default_data_type = default_data_type

    @tornado.gen.coroutine
    def handle_stream(self, stream, address):
        handler = ServerHandler(self.database_uri, self.default_data_type, stream)
        yield handler.handle()


class ServerHandler:
    # see https://python-hyper.org/projects/h2/en/stable/tornado-example.html
    def __init__(self, database_uri, default_data_type, stream):
        self.database_uri = database_uri
        self.default_data_type = default_data_type
        self.stream = stream

        config = h2.config.H2Configuration(client_side=False)
        self.conn = h2.connection.H2Connection(config=config)

    @tornado.gen.coroutine
    def handle(self):
        self.conn.initiate_connection()
        yield self.stream.write(self.conn.data_to_send())

        while True:
            try:
                data = yield self.stream.read_bytes(65535, partial=True)
                if not data:
                    break

                events = self.conn.receive_data(data)
                for event in events:
                    if isinstance(event, h2.events.RequestReceived):
                        self.request_received(event.headers, event.stream_id)
                    elif isinstance(event, h2.events.DataReceived):
                        self.conn.reset_stream(event.stream_id)

                yield self.stream.write(self.conn.data_to_send())

            except tornado.iostream.StreamClosedError:
                break

    def _get_obj(self, stream_id):
        with db.connect(self.database_uri) as conn:
            if self.default_data_type == "application/json":
                column = "json"
            elif self.default_data_type == "application/cbor":
                column = "cbor"
            else:
                raise ValueError(
                    f"Unexpected default_data_type = {self.default_data_type}"
                )
            cur = conn.cursor()
            cur.execute(
                f"SELECT {column}, http_status FROM objects LIMIT 1;"
            )
            cur.execute(
                f"""
                SELECT {column}, http_status
                FROM synced_objects
                WHERE msg_id = %(id)s;
                """,
                {"id": str(stream_id)},
            )
            res = cur.fetchone()
            if res is None:
                return b"", "404"
            obj, http_status = res
            if isinstance(obj, str):
                obj = obj.encode()
        return obj, str(http_status)

    def _get_dns(self, stream_id, resp_content_format):
        if resp_content_format == "application/dns-message":
            column = "classic_response"
        elif resp_content_format == "application/dns+cbor":
            column = "cbor_response"
        else:
            raise ValueError(f"Unexpected DNS format {resp_content_format}")
        with db.connect(self.database_uri) as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT {column}
                FROM synced_dns
                WHERE msg_id = %(id)s;
                """,
                {"id": str(stream_id)},
            )
            res = cur.fetchone()
            if res is None:
                return None
            return res[0]

    def _send_response(self, stream_id):
        obj, status = self._get_obj(stream_id)

        response_headers = (
            (":status", status),
            ("content-type", self.default_data_type),
        )
        self.conn.send_headers(stream_id, response_headers)
        self.conn.send_data(stream_id, obj, end_stream=True)

    def _respond_dns(self, headers, stream_id):
        if "accept" in headers and headers["accept"] != "*/*":
            resp_content_format = headers["accept"]
        elif "content-type" in headers:
            resp_content_format = headers["content-type"]
        else:
            resp_content_format = None
        resp = self._get_dns(stream_id, resp_content_format)

        response_headers = (
            (":status", "200" if resp is not None else "404"),
            ("content-type", resp_content_format),
        )
        self.conn.send_headers(stream_id, response_headers)
        self.conn.send_data(stream_id, resp or b"", end_stream=True)

    def request_received(self, headers, stream_id):
        headers = collections.OrderedDict(
            {k.decode(): v.decode() for k, v in headers}
        )
        if headers[":method"] == "POST":
            if headers["content-type"] in [
                "application/dns-message", "application/dns+cbor",
            ]:
                return self._respond_dns(headers, stream_id)
            if headers["content-type"] == "application/dns+cbor;packed=1":
                response_headers = (
                    ":status", "415",
                )
                self.conn.send_headers(stream_id, response_headers)
                self.conn.send_data(stream_id, b"", end_stream=True)
            if headers["accept"] == "application/dns+cbor;packed=1":
                response_headers = (
                    ":status", "501",
                )
                self.conn.send_headers(stream_id, response_headers)
                self.conn.send_data(stream_id, b"", end_stream=True)
        self._send_response(stream_id)



def existing_path(parser, arg):
    path = pathlib.Path(arg)
    if not path.exists():
        parser.error(f"File {arg} does not exist")
    return path


def hostportsplit_helper(parser, arg):
    if arg.isnumeric():
        raise parser.error(
            f"Invalid argument to --bind. Did you mean --bind :{arg}?"
        )

    try:
        pseudoparsed = urllib.parse.SplitResult(None, arg, None, None, None)
        bind = pseudoparsed.hostname, pseudoparsed.port
        if bind[1] is None:
            return bind[0], 443
        return bind
    except ValueError:
        raise parser.error(
            f"Invalid argument to --bind. Did you mean --bind '[{arg}]'?"
        )


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bind",
        help="Host and/or port to bind to",
        type=lambda arg: hostportsplit_helper(parser, arg),
        default=(None, 443),
    )
    parser.add_argument(
        "--credentials",
        required=True,
        help="JSON file pointing to credentials for the server's identity/ies.",
        type=lambda arg: existing_path(parser, arg)
    )
    parser.add_argument(
        "db_uri",
        help="The URI to the database containing objects and DNS messages.",
    )
    parser.add_argument(
        "default_data_type",
        choices=["application/json", "application/cbor"],
        help="Select default data type for responses.",
    )
    args = parser.parse_args()

    with open(args.credentials) as credfile:
        creds = cbor2.loads(cbor_diag.diag2cbor(credfile.read()))
    server_id = sorted(creds.keys())[0]
    client_id = creds[server_id]["dtls"]["client-identity"]["hex"]
    psk_table = {
        client_id: bytes.fromhex(creds[server_id]["dtls"]["psk"]["hex"])
    }

    def psk_server_callback(identity):
        return psk_table.get(identity, b"")

    ssl_ctx = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_SERVER)
    ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ssl_ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    ssl_ctx.set_ciphers("PSK-AES128-CBC-SHA256")
    ssl_ctx.set_alpn_protocols(["h2"])
    ssl_ctx.set_psk_server_callback(psk_server_callback, server_id)

    server = H2Server(args.db_uri, args.default_data_type, ssl_options=ssl_ctx)
    server.listen(address=args.bind[0], port=args.bind[1])
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
