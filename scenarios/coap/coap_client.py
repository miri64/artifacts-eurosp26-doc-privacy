#! /usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

import asyncio
import argparse
import math
import os
import pathlib
import re
import time

import aiocoap
import aiocoap.error
import aiocoap.cli.client
import aiocoap.proxy.client
import aiocoap.tokenmanager
import psycopg2 as db

from aiocoap.numbers.contentformat import ContentFormat
from aiocoap.optiontypes import BlockOption


import coap_server


def block_exp_from_block_size(block_size):
    if block_size < 16:
        return 0
    elif block_size > 1024:
        return 6
    return int(math.log2(block_size // 16))


async def send_requests(context, args):
    tm_next_token = aiocoap.tokenmanager.TokenManager.next_token

    if args.block_size is not None:
        block_exp = block_exp_from_block_size(args.block_size)
        block2 = BlockOption.BlockwiseTuple(
            0, 0, block_exp
        )
    else:
        block_exp = 6
        block2 = None

    if args.default_data_type == "application/json":
        query_column = "json_query"
    elif args.default_data_type == "application/cbor":
        query_column = "cbor_query"
    else:
        raise ValueError("Unexpected default data type {args.default_data_type}")

    if args.default_dns_type == "application/dns-message":
        dns_column = "classic_query"
        dns_content_format = args.default_dns_type
    elif args.default_dns_type.startswith("application/dns+cbor"):
        dns_column = "cbor_query"
        dns_content_format = "application/dns+cbor"
    else:
        raise ValueError("Unexpected default data type {args.default_data_type}")

    if args.security == "dtls":
        scheme = "coaps"
    else:
        scheme = "coap"

    if args.proxy:
        context = aiocoap.proxy.client.ProxyForwarder(
            f"{scheme}://{args.proxy}", context
        )

    with db.connect(args.db_uri) as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, url, {query_column}, url_wo_query FROM objects;"
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
        "response_code",
        "response_payload",
        sep="\t",
    )
    for data_id, url, query, url_wo_query in rows:
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

        def next_token(self):
            token = tm_next_token(self)
            if data_type == 0:
                _id = data_id
            else:
                _id = dns_id
            with db.connect(args.db_uri) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO sync (msg_id, data_id, data_type, client_id)
                    VALUES (%(token)s, %(id)s, %(data_type)s, %(client_id)s);
                    """,
                    {
                        "token": token.hex(),
                        "id": _id,
                        "data_type": data_type,
                        "client_id": str(args.client_id)
                    },
                )
                conn.commit()
            return token

        aiocoap.tokenmanager.TokenManager.next_token = next_token

        code = aiocoap.FETCH
        coap_url = f"{scheme}://{args.dns_server}"
        request = aiocoap.Message(
            code=code,
            accept=(
                coap_server.DNS_CONTENT_FORMATS[args.default_dns_type]
                if ";packed=" in args.default_dns_type
                else None
            ),
            payload=dns_query,
            uri=coap_url,
            content_format=coap_server.DNS_CONTENT_FORMATS[dns_content_format],
            block2=block2,
        )
        request.remote.maximum_block_size_exp = block_exp
        response = await context.request(request).response
        with db.connect(args.db_uri) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                DELETE FROM sync
                WHERE data_id = %(dns_id)s AND data_type = 1
                    AND client_id = %(client_id)s;
                """,
                {"dns_id": dns_id, "client_id": str(args.client_id)},
            )
            conn.commit()
        assert response.payload, "Server did not provide a response"
        assert response.opt.content_format == coap_server.DNS_CONTENT_FORMATS[
            args.default_dns_type
        ], "Server did not respond with a DNS response"
        print(
            time.time(),
            os.environ.get("WPAN_SIMULATION_PREFIX"),
            os.environ.get("UPSTREAM_PREFIX"),
            "dns",
            dns_name,
            dns_type,
            url,
            args.default_dns_type,
            response.code,
            response.payload.hex(),
            sep="\t",
        )

        data_type = 0
        if query and (len(url) > 32):
            code = aiocoap.FETCH
            coap_url = re.sub(r"^https?://", f"{scheme}://", url_wo_query)
        else:
            code = aiocoap.GET
            coap_url = re.sub(r"^https?://", f"{scheme}://", url)
        if isinstance(query, str):
            query = query.encode()
        request = aiocoap.Message(
            code=code,
            payload=query or b"",
            uri=coap_url,
            content_format=ContentFormat.by_media_type(args.default_data_type),
            block2=block2,
        )
        request.remote = aiocoap.message.UndecidedRemote(
            scheme,
            args.coap_server,
        )
        request.opt.uri_host = args.coap_server
        request.remote.maximum_block_size_exp = block_exp
        response = await context.request(request).response
        with db.connect(args.db_uri) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                DELETE FROM sync
                WHERE data_id = %(data_id)s AND data_type = 0
                    AND client_id = %(client_id)s;
                """,
                {"data_id": data_id, "client_id": str(args.client_id)},
            )
            conn.commit()
        print(
            time.time(),
            os.environ.get("WPAN_SIMULATION_PREFIX"),
            os.environ.get("UPSTREAM_PREFIX"),
            "data",
            "",
            "",
            url,
            args.default_data_type,
            response.code,
            response.payload.hex(),
            sep="\t",
        )
        stop = time.time()
        if args.delay > 0 and (stop - start) < args.delay:
            await asyncio.sleep(args.delay - (stop - start))


def valid_filename(parser, arg):
    path = pathlib.Path(arg)
    if path.exists():
        return path
    parser.error(
        f"The file “{arg}” does not ex39c9788e-77a9-44db-a92b-946e2483fd16ist!"
    )


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
        help="Client ID used for synchronization",
    )
    parser.add_argument(
        "--block-size",
        "-b",
        type=int,
        default=None,
        help="Block size in bytes (will be rounded down to next legal block size, "
        "capped at 16)",
    )
    parser.add_argument(
        "--proxy",
        "-p",
        help="Proxy hostname to send requests over to the server(s)",
    )
    parser.add_argument(
        "--security",
        "-s",
        choices=["dtls", "oscore"],
        help="Security mode to use for the DoC and CoAP requests",
    )
    parser.add_argument(
        "--credentials",
        help="Load credentials to use from a given file",
        type=lambda arg: valid_filename(parser, arg),
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
        "coap_server",
    )
    parser.add_argument(
        "dns_server",
    )
    args = parser.parse_args()

    context = await aiocoap.Context.create_client_context()
    try:
        if args.credentials:
            aiocoap.cli.client.apply_credentials(
                context,
                args.credentials,
                parser.error,
            )
        await send_requests(context, args)
    finally:
        await context.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
