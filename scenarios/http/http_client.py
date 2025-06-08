#! /usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

import argparse
import asyncio
import os
import re
import ssl
import time

import cbor_diag
import cbor2
import h2.connection
import httpx
import psycopg2 as db

from http_server import existing_path


async def send_requests(client, args, parser):
    h2_next_stream_id = h2.connection.H2Connection.get_next_available_stream_id

    with db.connect(args.db_uri) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM sync
            WHERE client_id = %(client_id)s;
            """,
            {"client_id": str(args.client_id)},
        )
        conn.commit()

    if args.default_data_type == "application/json":
        query_column = "json_query"
    elif args.default_data_type == "application/cbor":
        query_column = "cbor_query"
    else:
        raise ValueError("Unexpected default data type {args.default_data_type}")

    if args.default_dns_type == "application/dns-message":
        dns_column = "classic_query"
        dns_content_type = args.default_dns_type
    elif args.default_dns_type.startswith("application/dns+cbor"):
        dns_column = "cbor_query"
        dns_content_type = "application/dns+cbor"
    else:
        raise ValueError("Unexpected default data type {args.default_data_type}")

    if args.proxy:
        # TODO
        pass

    with db.connect(args.db_uri) as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, url, {query_column}, url_wo_query FROM objects LIMIT 10;"
            # f"SELECT id, url, {query_column}, url_wo_query FROM objects;"
        )
        rows = cur.fetchall()

    print(
        "timestamp",
        "wpan_prefix",
        "upstream_prefix",
        "type",
        "query_name",
        "query_type",
        "url",
        "media_type",
        "response_status",
        "obj_id",
        "response_payload",
        sep="\t",
    )
    for data_id, url, query, url_wo_query in rows:
        if isinstance(query, memoryview):
            query = query.tobytes()
        start = time.time()

        data_type = 1
        with db.connect(args.db_uri) as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT id, name, type, {dns_column}
                FROM dns
                WHERE obj_id = %(data_id)s
                ORDER BY array_position(array['HTTPS', 'AAAA', 'A'], dns.type)
                ASC
                LIMIT 1;
                """,
                {"data_id": data_id},
            )
            res = cur.fetchone()
            assert res, f"No DNS query found for {url} (id={data_id})"
            dns_id, dns_name, dns_type, dns_query = res
            if isinstance(dns_query, memoryview):
                dns_query = dns_query.tobytes()

        def next_stream_id(self):
            stream_id = h2_next_stream_id(self)
            if data_type == 0:
                _id = data_id
            else:
                _id = dns_id
            with db.connect(args.db_uri) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO sync (msg_id, data_id, data_type, client_id)
                    VALUES (%(stream_id)s, %(id)s, %(data_type)s, %(client_id)s);
                    """,
                    {
                        "stream_id": str(stream_id),
                        "id": _id,
                        "data_type": data_type,
                        "client_id": str(args.client_id)
                    },
                )
                conn.commit()
            return stream_id

        h2.connection.H2Connection.get_next_available_stream_id = next_stream_id

        response = await client.request(
            "POST",
            f"https://{args.dns_server}",
            headers={
                "content-type": dns_content_type,
            },
            data=dns_query,
        )
        response_timestamp = time.time()
        with db.connect(args.db_uri) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT msg_id FROM sync
                WHERE data_id = %(dns_id)s AND data_type = 1
                    AND client_id = %(client_id)s;
                """,
                {"dns_id": dns_id, "client_id": str(args.client_id)},
            )
            res = cur.fetchall()
            assert res
            streams = [row[0] for row in res]
            cur.execute(
                """
                DELETE FROM sync
                WHERE data_id = %(dns_id)s AND data_type = 1
                    AND client_id = %(client_id)s;
                """,
                {"dns_id": dns_id, "client_id": str(args.client_id)},
            )
            conn.commit()
        assert response.content, f"Server did not provide a response {response}"
        assert response.headers["content-type"] == args.default_dns_type
        for stream_id in streams:
            print(
                response_timestamp,
                os.environ.get("WPAN_SIMULATION_PREFIX"),
                os.environ.get("UPSTREAM_PREFIX"),
                "dns",
                dns_name,
                dns_type,
                url,
                args.default_dns_type,
                response.status_code,
                stream_id,
                response.content.hex(),
                sep="\t",
            )

        data_type = 0
        headers = {}
        if query and (len(url) > 32):
            code = "POST"
            http_url = re.sub(
                r"^https?://[^/]+", f"https://{args.http_server}",
                url_wo_query
            )
            headers["content-type"] = args.default_data_type
        else:
            code = "GET"
            http_url = re.sub(
                r"^https?://[^/]+", f"https://{args.http_server}",
                url
            )
        if isinstance(query, str):
            query = query.encode()
        response = await client.request(
            code,
            http_url,
            headers=headers,
            data=query or b"",
        )
        response_timestamp = time.time()
        with db.connect(args.db_uri) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT msg_id FROM sync
                WHERE data_id = %(data_id)s AND data_type = 0
                    AND client_id = %(client_id)s;
                """,
                {"data_id": data_id, "client_id": str(args.client_id)},
            )
            res = cur.fetchall()
            assert res
            streams = [row[0] for row in res]
            cur.execute(
                """
                DELETE FROM sync
                WHERE data_id = %(data_id)s AND data_type = 0
                    AND client_id = %(client_id)s;
                """,
                {"data_id": data_id, "client_id": str(args.client_id)},
            )
            conn.commit()
        for stream_id in streams:
            print(
                response_timestamp,
                os.environ.get("WPAN_SIMULATION_PREFIX"),
                os.environ.get("UPSTREAM_PREFIX"),
                "data",
                "",
                "",
                url,
                args.default_data_type,
                response.status_code,
                stream_id,
                response.content.hex(),
                sep="\t",
            )
        stop = time.time()
        if args.delay > 0 and (stop - start) < args.delay:
            await asyncio.sleep(args.delay - (stop - start))


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--client-id",
        "-i",
        type=int,
        default=0,
        help="Client ID used for synchronization",
    )
    parser.add_argument(
        "--delay",
        "-d",
        type=float,
        default=0,
        help="Delay between requests",
    )
    parser.add_argument(
        "--credentials",
        required=True,
        help="JSON file pointing to credentials for the server's identity/ies.",
        type=lambda arg: existing_path(parser, arg)
    )
    parser.add_argument(
        "--proxy",
        "-p",
        help="Proxy hostname to send requests over to the server(s)",
    )
    parser.add_argument(
        "db_uri",
        help="The URI to the database containing objects and DNS messages.",
    )
    parser.add_argument(
        "default_data_type",
        choices=["application/json", "application/cbor"],
        help="Select default data type for requests.",
    )
    parser.add_argument(
        "default_dns_type",
        choices=[
            "application/dns-message",
            "application/dns+cbor",
            "application/dns+cbor;packed=1",
        ],
        help="DNS content format to accept (application/dns+cbor;packed=1 uses "
        "application/dns+cbor as content format for queries, all other use the given "
        "type).",
    )
    parser.add_argument(
        "http_server",
    )
    parser.add_argument(
        "dns_server",
    )
    args = parser.parse_args()

    with open(args.credentials) as credfile:
        creds = cbor2.loads(cbor_diag.diag2cbor(credfile.read()))

    def psk_client_callback(identity):
        client_id = creds[identity]["dtls"]["client-identity"]["hex"]
        # ssl for some reason only expects string identities so use have the hex
        return (client_id, bytes.fromhex(creds[identity]["dtls"]["psk"]["hex"]))

    ssl_ctx = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_CLIENT)
    ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ssl_ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    ssl_ctx.set_ciphers("PSK-AES128-CBC-SHA256")
    ssl_ctx.set_alpn_protocols(["h2"])
    ssl_ctx.set_psk_client_callback(psk_client_callback)

    async with httpx.AsyncClient(http1=False, http2=True, verify=ssl_ctx) as client:
        await send_requests(client, args, parser)



if __name__ == "__main__":
    asyncio.run(main())
