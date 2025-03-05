#! /usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

import argparse
import asyncio
import sqlite3

import aiocoap.cli.client
import aiocoap.proxy.server
import aiocoap.tokenmanager

import coap_server


class Proxy(aiocoap.proxy.server.ForwardProxyWithPooledObservations):
    def __init__(self, database_file, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.database_file = database_file
        self.next_token = aiocoap.tokenmanager.TokenManager.next_token

    async def render(self, request):
        old_token = request.token

        def next_token(inner):
            new_token = self.next_token(inner)
            with sqlite3.connect(self.database_file, isolation_level="IMMEDIATE", autocommit=True) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE sync
                    SET msg_id = ?
                    WHERE msg_id = ?;
                    """,
                    (new_token, old_token),
                )
                conn.commit()
            return new_token

        aiocoap.tokenmanager.TokenManager.next_token = next_token
        response = await super().render(request)

        aiocoap.tokenmanager.TokenManager.next_token = self.next_token
        return response


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "sqlite3_file",
        type=lambda arg: coap_server.valid_filename(parser, arg),
        help="The SQLite database containing objects and DNS messages.",
    )
    aiocoap.cli.common.add_server_arguments(parser)
    args = parser.parse_args()

    coap_server.ensure_database_views(args.sqlite3_file)
    outgoing_context = await aiocoap.Context.create_client_context()
    try:
        if args.credentials:
            aiocoap.cli.client.apply_credentials(
                outgoing_context,
                args.credentials,
                parser.error,
            )
        proxy = Proxy(args.sqlite3_file, outgoing_context)
        await aiocoap.cli.common.server_context_from_arguments(proxy, args)
        await asyncio.get_running_loop().create_future()
    finally:
        await outgoing_context.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
