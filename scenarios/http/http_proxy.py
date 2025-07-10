#! /usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

import argparse
import asyncio
import collections
import ssl
import sys
import urllib.parse

import cbor_diag
import cbor2
import h2.config
import h2.connection
import h2.events
import httpx
import psycopg2 as db
import tornado

from http_server import H2Server, hostportsplit_helper, existing_path


last_stream_id = 0


class ForwardProxyHandler:
    client = None

    def __init__(self, database_uri, stream, *args, **kwargs):
        self.database_uri = database_uri
        self.stream = stream
        self.next_stream_id = h2.connection.H2Connection.get_next_available_stream_id
        self.upstream_method = None
        self.upstream_url = None
        self.upstream_headers = None

        config = h2.config.H2Configuration(client_side=False)
        self.conn = h2.connection.H2Connection(config=config)

    async def get_response_from_upstream(self, stream_id, data=None):
        old_stream_id = stream_id

        def next_stream_id(inner):
            # ensures that stream id stay unique even in p2 case
            global last_stream_id
            new_stream_id = self.next_stream_id(inner)
            if new_stream_id > 0:
                while new_stream_id <= last_stream_id:
                    new_stream_id += 2
                last_stream_id = new_stream_id
            with db.connect(self.database_uri) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE sync
                    SET msg_id = %(new_stream_id)s
                    WHERE msg_id = %(old_stream_id)s;
                    """,
                    {
                        "new_stream_id": str(new_stream_id),
                        "old_stream_id": str(old_stream_id),
                    },
                )
                conn.commit()
            print(old_stream_id, new_stream_id, sep="\t")
            sys.stdout.flush()
            return new_stream_id

        h2.connection.H2Connection.get_next_available_stream_id = next_stream_id

        response = await self.client.request(
            self.upstream_method,
            self.upstream_url,
            headers=self.upstream_headers,
            data=data,
        )

        h2.connection.H2Connection.get_next_available_stream_id = self.next_stream_id

        response_headers = collections.OrderedDict(
            [(":status", str(response.status_code))]
        )
        response_headers.update(response.headers)

        self.conn.send_headers(stream_id, list(response_headers.items()))
        self.conn.send_data(stream_id, response.content, end_stream=True)
        self.upstream_headers = None
        self.upstream_method = None
        self.upstream_url = None

    async def data_received(self, data, stream_id):
        await self.get_response_from_upstream(stream_id, data)

    async def handle(self):
        self.conn.initiate_connection()
        await self.stream.write(self.conn.data_to_send())

        while True:
            try:
                data = await self.stream.read_bytes(65535, partial=True)
                if not data:
                    break

                events = self.conn.receive_data(data)
                for event in events:
                    if isinstance(event, h2.events.RequestReceived):
                        await self.request_received(event.headers, event.stream_id)
                    elif isinstance(event, h2.events.DataReceived):
                        if self.upstream_headers and int(
                            self.upstream_headers.get("content-length", 0)
                        ) > 0:
                            fc_length = event.flow_controlled_length
                            self.conn.acknowledge_received_data(fc_length, event.stream_id)
                            await self.data_received(event.data, event.stream_id)

                await self.stream.write(self.conn.data_to_send())

            except tornado.iostream.StreamClosedError:
                break

    async def request_received(self, headers, stream_id):
        headers = collections.OrderedDict(
            {k.decode(): v.decode() for k, v in headers}
        )

        self.upstream_method = headers.pop(":method")
        scheme = headers.pop(":scheme")
        authority = headers.pop(":authority")
        path = urllib.parse.quote(headers.pop(":path"))
        self.upstream_url = f"{scheme}://{authority}{path}"
        self.upstream_headers = headers
        if int(self.upstream_headers.get("content-length", 0)) == 0:
            await self.get_response_from_upstream(stream_id)


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

    server_ctx = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_SERVER)
    server_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    server_ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    server_ctx.set_ciphers("PSK-AES128-CBC-SHA256")
    server_ctx.set_alpn_protocols(["h2"])
    server_ctx.set_psk_server_callback(psk_server_callback, server_id)

    def psk_client_callback(identity):
        client_id = creds[identity]["dtls"]["client-identity"]["hex"]
        return (client_id, bytes.fromhex(creds[identity]["dtls"]["psk"]["hex"]))

    client_ctx = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_CLIENT)
    client_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    client_ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    client_ctx.check_hostname = False
    client_ctx.verify_mode = ssl.CERT_NONE
    client_ctx.set_ciphers("PSK-AES128-CBC-SHA256")
    client_ctx.set_alpn_protocols(["h2"])
    client_ctx.set_psk_client_callback(psk_client_callback)

    ForwardProxyHandler.client = httpx.AsyncClient(
        http1=False, http2=True, verify=client_ctx
    )
    H2Server.handler = ForwardProxyHandler
    try:
        server = H2Server(
            args.db_uri,
            ssl_options=server_ctx,
        )

        print("old_token", "new_token", sep="\t")
        server.listen(address=args.bind[0], port=args.bind[1])
        await asyncio.Event().wait()
    finally:
        ForwardProxyHandler.client.close()


if __name__ == "__main__":
    asyncio.run(main())
