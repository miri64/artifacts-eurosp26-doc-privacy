#! /usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

import asyncio
import argparse
import pathlib
import sys

import aiocoap
import aiocoap.cli.common
import aiocoap.error
import aiocoap.numbers.constants
import aiocoap.resource
import psycopg2 as db
import psycopg2.errors as db_errors

from aiocoap.numbers import codes
from aiocoap.numbers.contentformat import ContentFormat


DNS_CONTENT_FORMATS = {
    "application/dns-message": 553,
    "application/dns+cbor": 53,
    "application/dns+cbor;packed=1": 54,
}


class Resource(aiocoap.resource.Resource, aiocoap.resource.PathCapable):
    def __init__(self, database_uri, default_data_type):
        self.database_uri = database_uri
        self.default_data_type = (
            aiocoap.numbers.contentformat.ContentFormat.by_media_type(default_data_type)
        )

    def _get_obj(self, request):
        with db.connect(self.database_uri) as conn:
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
                f"""
                SELECT {column}, http_status
                FROM synced_objects
                WHERE msg_id = %(id)s;
                """,
                {"id": request.token.hex()},
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
        with db.connect(self.database_uri) as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT {column}
                FROM synced_dns
                WHERE msg_id = %(id)s;
                """,
                {"id": request.token.hex()},
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


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "db_uri",
        help="The URI to the database containing objects and DNS messages.",
    )
    parser.add_argument(
        "default_data_type",
        choices=["application/json", "application/cbor"],
        help="Select default data type for responses.",
    )
    aiocoap.cli.common.add_server_arguments(parser)
    args = parser.parse_args()

    site = Resource(
        args.db_uri,
        args.default_data_type,
    )
    await aiocoap.cli.common.server_context_from_arguments(site, args)

    print("starting server")
    await asyncio.get_running_loop().create_future()


if __name__ == "__main__":
    asyncio.run(main())
