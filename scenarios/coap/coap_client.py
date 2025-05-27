#! /usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

import asyncio
import argparse
import collections
import math
import os
import pathlib
import random
import re
import time

import aiocoap
import aiocoap.error
import aiocoap.cli.client
import aiocoap.messagemanager
import aiocoap.proxy.client
import aiocoap.tokenmanager
import aiocoap.transports.oscore
from aiocoap.util import hostportsplit
import psycopg2 as db

from aiocoap.numbers.contentformat import ContentFormat
from aiocoap.optiontypes import BlockOption


import coap_server


class OSCOREProxyForwarder(aiocoap.proxy.client.ProxyForwarder):
    def request(self, message, **kwargs):
        message.is_inner = False
        return super().request(message, **kwargs)


def block_exp_from_block_size(block_size):
    if block_size < 16:
        return 0
    elif block_size > 1024:
        return 6
    return int(math.log2(block_size // 16))


async def send_requests(context, args, parser):
    tm_next_token = aiocoap.tokenmanager.TokenManager.next_token
    mm_next_mid = aiocoap.messagemanager.MessageManager._next_message_id
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
        if args.security == "oscore":
            assert args.credentials and (args.classic or args.proxy_credentials)
            if args.proxy_credentials:
                aiocoap.cli.client.apply_credentials(
                    context,
                    args.proxy_credentials,
                    parser.error,
                )
            if args.classic:
                aiocoap.cli.client.apply_credentials(
                    context,
                    args.credentials,
                    parser.error,
                )
                context = aiocoap.proxy.client.ProxyForwarder(
                    f"{scheme}://{args.proxy}", context
                )
            else:
                proxy_context = OSCOREProxyForwarder(
                    f"{scheme}://{args.proxy}", context
                )
                context = await aiocoap.Context.create_client_context()
                for ri in context.request_interfaces:
                    if isinstance(ri, aiocoap.transports.oscore.TransportOSCORE):
                        ri._wire = proxy_context
                aiocoap.cli.client.apply_credentials(
                    context,
                    args.credentials,
                    parser.error,
                )
        else:
            if args.credentials:
                aiocoap.cli.client.apply_credentials(
                    context,
                    args.credentials,
                    parser.error,
                )
            context = aiocoap.proxy.client.ProxyForwarder(
                f"{scheme}://{args.proxy}", context
            )
    elif args.credentials:
        aiocoap.cli.client.apply_credentials(
            context,
            args.credentials,
            parser.error,
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
        "token",
        "response_payload",
        sep="\t",
    )
    if args.randomize:
        first_token = random.randint(0x0000, 0xff)
        token_pool = list(range(first_token, first_token + (len(rows) * 100)))
        # shuffle token pool to guarantee random tokens
        random.shuffle(token_pool)
        mid_pool = list(range(0x0000, 0xffff + 1))
        random.shuffle(mid_pool)
    else:
        token_pool = []
        mid_pool = []
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
            if token_pool:
                token = token_pool.pop().to_bytes(8, "big").lstrip(b"\0")
            else:
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

        def next_mid(self):
            mid = mm_next_mid(self)
            if mid_pool:
                mid = mid_pool[mid]
            return mid

        aiocoap.tokenmanager.TokenManager.next_token = next_token
        aiocoap.messagemanager.MessageManager._next_message_id = next_mid

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
        if args.security == "oscore" and not args.classic:
            request.is_inner = True
        request.remote.maximum_block_size_exp = block_exp
        response = await context.request(request).response
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
            tokens = [row[0] for row in res]
            cur.execute(
                """
                DELETE FROM sync
                WHERE data_id = %(dns_id)s AND data_type = 1
                    AND client_id = %(client_id)s;
                """,
                {"dns_id": dns_id, "client_id": str(args.client_id)},
            )
            conn.commit()
        assert response.payload, f"Server did not provide a response {response}"
        assert response.opt.content_format == coap_server.DNS_CONTENT_FORMATS[
            args.default_dns_type
        ], "Server did not respond with a DNS response"
        for token in tokens:
            print(
                response_timestamp,
                os.environ.get("WPAN_SIMULATION_PREFIX"),
                os.environ.get("UPSTREAM_PREFIX"),
                "dns",
                dns_name,
                dns_type,
                url,
                args.default_dns_type,
                response.code,
                token,
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
            content_format=(
                ContentFormat.by_media_type(args.default_data_type)
                if code == aiocoap.FETCH
                else None
            ),
            block2=block2,
        )
        request.remote = aiocoap.message.UndecidedRemote(
            scheme,
            args.coap_server,
        )
        if args.security == "oscore" and not args.classic:
            request.is_inner = True
        request.opt.uri_host = args.coap_server
        request.remote.maximum_block_size_exp = block_exp
        response = await context.request(request).response
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
            tokens = [row[0] for row in res]
            cur.execute(
                """
                DELETE FROM sync
                WHERE data_id = %(data_id)s AND data_type = 0
                    AND client_id = %(client_id)s;
                """,
                {"data_id": data_id, "client_id": str(args.client_id)},
            )
            conn.commit()
        for token in tokens:
            print(
                response_timestamp,
                os.environ.get("WPAN_SIMULATION_PREFIX"),
                os.environ.get("UPSTREAM_PREFIX"),
                "data",
                "",
                "",
                url,
                args.default_data_type,
                response.code,
                token,
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


def hostportsplit_helper(parser, arg):
    if arg.isnumeric():
        raise parser.error(
            f"Invalid argument to --bind. Did you mean --bind :{arg}?"
        )

    try:
        bind = hostportsplit(arg)
        if bind[0] is None:
            return ("", bind[1])
        return bind
    except ValueError:
        raise parser.error(
            f"Invalid argument to --bind. Did you mean --bind '[{arg}]'?"
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
        "--bind",
        help="Host and/or port to bind to",
        type=lambda arg: hostportsplit_helper(parser, arg),
        default=None,
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
        "--classic",
        "-c",
        help="Use classic OSCORE instead of Onion OSCORE if --security is \"oscore\"",
        action="store_true",
    )
    parser.add_argument(
        "--proxy",
        "-p",
        help="Proxy hostname to send requests over to the server(s)",
    )
    parser.add_argument(
        "--randomize",
        "-r",
        help="Randomize CoAP message ID and token",
        action="store_true",
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
        "--proxy-credentials",
        help="Load proxy credentials to use from a given file. "
        "Only used when --proxy is set and --security is \"oscore\".",
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

    orig_protect = aiocoap.oscore.CanProtect.protect

    def protect(self, unprotected_message, request_id=None, *, kid_context=True):
        protected_message, request_id = orig_protect(
            self, unprotected_message, request_id=request_id, kid_context=kid_context
        )
        protected_message.opt.proxy_scheme = unprotected_message.opt.proxy_scheme
        protected_message = protected_message
        return protected_message, request_id

    aiocoap.oscore.CanProtect.protect = protect
    context = await aiocoap.Context.create_client_context(local_bind=args.bind)
    try:
        await send_requests(context, args, parser)
    finally:
        await context.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
