#! /usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

import argparse
import asyncio

import aiocoap.cli.client
import aiocoap.cli.common
import aiocoap.proxy.server
import aiocoap.tokenmanager
import psycopg2 as db

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
            with db.connect(self.database_file) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE sync
                    SET msg_id = %(new_token)s
                    WHERE msg_id = %(old_token)s;
                    """,
                    {"new_token": new_token.hex(), "old_token": old_token.hex()},
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
