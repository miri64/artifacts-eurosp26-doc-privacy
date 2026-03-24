#! /usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

import argparse
import csv
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse

import dns.rdatatype


import pprint


TSHARK_PATH = os.environ.get("TSHARK_PATH")
FIELDS = [
    "frame.protocols",
    "dns.flags.response",
    "dns.qry.name",
    "dns.qry.type",
    "dns.resp.name",
    "dns.resp.type",
    "udp.payload",
]
FIELDS_SIMPLIFIED = {
    "frame.protocols": "protocols",
    "dns.flags.response": "is_response",
    "dns.qry.name": "query_name",
    "dns.qry.type": "query_type",
    "dns.resp.name": "response_names",
    "dns.resp.type": "response_types",
    "udp.payload": "dns_msg",
}


def canonize_name(name):
    return "." if name == "<Root>" else f"{name}."


def remove_tid(data_hex):
    return f"0000{data_hex[4:]}" 


FIELDS_CAST = {
    "frame.protocols": lambda x: x,
    "dns.flags.response": lambda x: x in ["1", "True"],
    "dns.qry.name": canonize_name,
    "dns.qry.type": lambda x: dns.rdatatype.RdataType(int(x)).name,
    "dns.resp.name": lambda x: "|".join(canonize_name(n) for n in x.split("|")),
    "dns.resp.type": lambda x: "|".join(
        dns.rdatatype.RdataType(int(t)).name for t in x.split("|")
    ),
    "udp.payload": remove_tid,
}
OUTPUT_FIELDS = [
    "url",
    "http_status",
    "obj_len",
    "obj",
    "a_q_dns_msg",
    "a_q_protocols", 
    "a_q_query_name",
    "a_q_query_type",
    "a_q_response_names",
    "a_q_response_types",
    "a_r_dns_msg",
    "a_r_protocols",
    "a_r_query_name",
    "a_r_query_type",
    "a_r_response_names",
    "a_r_response_types",
    "aaaa_q_dns_msg",
    "aaaa_q_protocols", 
    "aaaa_q_query_name",
    "aaaa_q_query_type",
    "aaaa_q_response_names",
    "aaaa_q_response_types",
    "aaaa_r_dns_msg",
    "aaaa_r_protocols",
    "aaaa_r_query_name",
    "aaaa_r_query_type",
    "aaaa_r_response_names",
    "aaaa_r_response_types",
    "https_q_dns_msg",
    "https_q_protocols", 
    "https_q_query_name",
    "https_q_query_type",
    "https_q_response_names",
    "https_q_response_types",
    "https_r_dns_msg",
    "https_r_protocols",
    "https_r_query_name",
    "https_r_query_type",
    "https_r_response_names",
    "https_r_response_types",
]



class UnableToGetError(Exception):
    pass


class UnableToResolveError(Exception):
    pass


def curl(url, user_agent):
    try:
        response = subprocess.check_output(
            [
                "curl",
                "-w",
                "\n\t\n\t\n\tcanary\t%{response_code}",
                "-o",
                "-",
                "--connect-timeout",
                "10",
                "-s",
                "-A",
                user_agent,
                "-L",
                url
            ]
        )
    except subprocess.CalledProcessError as exc:
        raise UnableToGetError(f"Could not fetch URL: {exc}") from exc
    try:
        response = response.split(b"\n\t\n\t\n\tcanary\t")
        http_status, obj = int(response[1]), json.loads(response[0])
    except json.JSONDecodeError as exc:
        raise UnableToGetError(f"Unable to decode '{response}': {exc}") from exc
    return http_status, obj


def dig(url, sniff_interface=None):
    extra_args = []
    if sniff_interface is not None:
        extra_args = ["-i", sniff_interface]
    url_parse = urllib.parse.urlparse(url)
    with tempfile.NamedTemporaryFile() as fp:
        proc = subprocess.Popen(
            [
                TSHARK_PATH,
                "-E",
                "aggregator=|",
                "-w",
                fp.name
            ] + extra_args,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1)
        responded_records = set()
        for record in ["A", "AAAA", "HTTPS"]:
            try:
                response = subprocess.check_output(
                    ["dig", "@9.9.9.9", url_parse.hostname, record],
                    text=True,
                )
                if re.search(fr"\s+\d+\s+IN\s+{record}", response):
                    responded_records.add(dns.rdatatype.RdataType[record].value)
            except subprocess.CalledProcessError as exc:
                raise UnableToResolveError(
                    f"Unable to resolve {record} for {url}: {exc}"
                ) from exc
            # print(response)
        time.sleep(1)
        proc.terminate()

        out = subprocess.check_output(
            [
                TSHARK_PATH,
                "-Y",
                f'dns.qry.name=="{url_parse.hostname}" && (' + " || ".join(
                    f"dns.qry.type=={type}" for type in responded_records
                ) + ")",
                "-E",
                "aggregator=|",
                "-r",
                fp.name,
                "-Tfields",
            ] + [
                a for pair in [("-e", f) for f in FIELDS] for a in pair
            ],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        
        res = {}
        with io.StringIO(out) as pcap:
            reader = csv.DictReader(pcap, fieldnames=FIELDS, delimiter="\t")
            for row in reader:
                assert row["udp.payload"], f"Ooops, no payload for {url}: {row}"
                query_type = dns.rdatatype.RdataType(
                    int(row["dns.qry.type"])
                ).name.lower()
                for col in row:
                    if col in ["dns.flags.response"]:
                        continue
                    if row["dns.flags.response"] in ["1", "True"]:
                        msg_type = "r"
                    else:
                        msg_type = "q"
                    res[
                        f"{query_type}_{msg_type}_{FIELDS_SIMPLIFIED[col]}"
                    ] = FIELDS_CAST[col](row[col])
    return res


if __name__ == "__main__":
    if TSHARK_PATH is None:
        TSHARK_PATH = subprocess.check_output(
            "command -v tshark",
            text=True,
            shell=True,
        ).strip()
        if not TSHARK_PATH:
            print("Script requires TShark to be installed", file=sys.stderr)
            sys.exit(1)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--sniff-interface",
        help="Interface to sniff for DNS on",
        default=None,
    )
    parser.add_argument(
        "-0",
        "--header",
        help="Print header for CSV",
        action="store_true"
    )
    args = parser.parse_args()
    reader = csv.DictReader(
        sys.stdin, fieldnames=["url", "req_user_agent", "resp_content_length"]
    )
    writer = csv.DictWriter(
        sys.stdout,
        fieldnames=OUTPUT_FIELDS,
        delimiter=";",
        quotechar="'",
        quoting=csv.QUOTE_MINIMAL
    )
    if args.header:
        writer.writeheader()
        sys.exit(0)
    for row in reader:
        if all(key == row[key] for key in row):
            # that's the header...
            continue
        try:
            http_status, obj = curl(row["url"], row["req_user_agent"])
        except UnableToGetError as exc:
            print(f"Unable to get {row['url']}:", exc, file=sys.stderr)
            continue
        obj_str = json.dumps(obj, separators=(",", ":"))
        if not obj or len(obj_str) > 1000:
            continue
        try:
            res = dig(row["url"], args.sniff_interface)
        except UnableToResolveError as exc:
            print(f"Unable to resolve:", exc, file=sys.stderr)
            continue
        res["url"] = row["url"]
        res["http_status"] = http_status
        res["obj"] = obj_str
        res["obj_len"] = len(obj_str)
        writer.writerow(res)
