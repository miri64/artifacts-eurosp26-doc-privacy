#! /usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

import asyncio
import argparse
import pathlib
import sqlite3
import sys

import aiocoap
import aiocoap.cli.common
import aiocoap.error
import aiocoap.numbers.constants
import aiocoap.resource

from aiocoap.numbers import codes
from aiocoap.numbers.contentformat import ContentFormat


DNS_CONTENT_FORMATS = {
    "application/dns-message": 553,
    "application/dns+cbor": 53,
    "application/dns+cbor;packed=1": 54,
}


class Resource(aiocoap.resource.Resource, aiocoap.resource.PathCapable):
    def __init__(self, database_file, default_data_type):
        self.database_file = database_file
        self.default_data_type = (
            aiocoap.numbers.contentformat.ContentFormat.by_media_type(default_data_type)
        )

    def _get_obj(self, request):
        with sqlite3.connect(self.database_file) as conn:
            if self.default_data_type == ContentFormat.JSON:
                column = "json"
            elif self.default_data_type == ContentFormat.CBOR:
                column = "cbor"
            else:
                raise ValueError(
                    f"Unexpected default_data_type = {self.default_data_type}"
                )
            cur = conn.cursor()
            cur.execute(
                f"SELECT {column}, http_status FROM synced_objects WHERE msg_id = ?;",
                (request.token,),
            )
            res = cur.fetchone()
            if res is None:
                raise aiocoap.error.NotFound
            obj, http_status = res
            if isinstance(obj, str):
                obj = obj.encode()
        if (http_status >= 200 and http_status < 400) or http_status >= 600:
            code = None
        else:
            code = (http_status // 100) << 5
            if http_status % 100 < 0b11111:
                code |= http_status % 100
            else:
                code |= 0b11111
        return obj, code

    def _get_dns(self, request, resp_content_format):
        if resp_content_format == DNS_CONTENT_FORMATS["application/dns-message"]:
            column = "classic_response"
        elif resp_content_format == DNS_CONTENT_FORMATS["application/dns+cbor"]:
            column = "cbor_response"
        else:
            raise ValueError(f"Unexpected DNS format {resp_content_format}")
        with sqlite3.connect(self.database_file) as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {column} FROM synced_dns WHERE msg_id = ?;", (request.token,),
            )
            res = cur.fetchone()
            if res is None:
                raise aiocoap.error.NotFound
            return res[0]

    def _render_response(self, request):
        obj, code = self._get_obj(request)
        return aiocoap.Message(
            payload=obj,
            code=code,
            content_format=self.default_data_type,
        )

    def _respond_dns(self, request):
        resp_content_format = request.opt.accept or request.opt.content_format
        return aiocoap.Message(
            payload=self._get_dns(request, resp_content_format),
            code=aiocoap.CONTENT,
            content_format=resp_content_format,
        )

    async def render_get(self, request):
        return self._render_response(request)

    async def render_post(self, request):
        return self._render_response(request)

    async def render_put(self, request):
        return self._render_response(request)

    async def render_fetch(self, request):
        if request.opt.content_format in DNS_CONTENT_FORMATS.values():
            if (
                request.opt.content_format
                == DNS_CONTENT_FORMATS["application/dns+cbor;packed=1"]
            ):
                raise aiocoap.UnsupportedContentFormat
            if (
                request.opt.accept
                == DNS_CONTENT_FORMATS["application/dns+cbor;packed=1"]
            ):
                # TODO implement
                raise aiocoap.NotImplemented
            return self._respond_dns(request)
        return self._render_response(request)


def valid_filename(parser, arg):
    path = pathlib.Path(arg)
    if path.exists():
        return path
    parser.error(
        f"The file “{arg}” does not ex39c9788e-77a9-44db-a92b-946e2483fd16ist!"
    )


def ensure_database_views(database_file):
    with sqlite3.connect(database_file) as conn:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE;")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sync (
                id INTEGER PRIMARY_KEY,
                msg_id TEXT NOT NULL,
                data_id INTEGER NOT NULL,
                data_type INTEGER NOT NULL,
                client_id TEXT NOT NULL
            );"""
        )
        cur.execute("CREATE INDEX IF NOT EXISTS sync_msg_id ON sync (msg_id);")
        cur.execute(
            """
            CREATE VIEW IF NOT EXISTS synced_objects AS
            SELECT
                objects.url AS url,
                objects.id AS object_id,
                sync.id AS sync_id,
                msg_id,
                http_status,
                json,
                cbor,
                json_query,
                url_wo_query,
                cbor_query
            FROM objects
            INNER JOIN sync ON objects.id = sync.data_id AND sync.data_type = 0;"""
        )
        cur.execute(
            """
            CREATE VIEW IF NOT EXISTS synced_dns AS
            SELECT
                dns.url AS url,
                dns.id AS dns_id,
                sync.id AS sync_id,
                msg_id,
                name
                type,
                query_add_names,
                query_add_types,
                classic_query,
                cbor_query,
                response_names,
                response_types,
                classic_response,
                cbor_response
            FROM dns
            INNER JOIN sync ON dns.id = sync.data_id AND sync.data_type = 1;"""
        )
        conn.commit()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "sqlite3_file",
        type=lambda arg: valid_filename(parser, arg),
        help="The SQLite database containing objects and DNS messages.",
    )
    parser.add_argument(
        "default_data_type",
        choices=["application/json", "application/cbor"],
        help="Select default data type for responses.",
    )
    aiocoap.cli.common.add_server_arguments(parser)
    args = parser.parse_args()

    ensure_database_views(args.sqlite3_file)
    site = Resource(
        args.sqlite3_file,
        args.default_data_type,
    )
    await aiocoap.cli.common.server_context_from_arguments(site, args)

    print("starting server")
    await asyncio.get_running_loop().create_future()


if __name__ == "__main__":
    asyncio.run(main())
