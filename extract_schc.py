#! /usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

import argparse
import binascii
import csv
import datetime
import gzip
import io
import pathlib
import re
import sys
import unittest.mock
import warnings


from scenarios.schc.schc import OpenSCHCLoader


SCRIPT_PATH = pathlib.Path(__file__).resolve().parent
OPENSCHC_PATH = SCRIPT_PATH / "scenarios" / "schc" / "openschc" / "src"
ETH_COL_TYPES = {
    "frame.number": int,
    "eth.src": lambda x: bytes.fromhex(x.replace(":", "")),
    "eth.dst": lambda x: bytes.fromhex(x.replace(":", "")),
    "eth.type": lambda x: int(x[2:], base=16),
    "eth.payload": bytes.fromhex,
}
ROUTE_COL_TYPES = {
    "eth": bytes.fromhex,
}


def convert_columns(row, conversion_map):
    for col in conversion_map:
        row[col] = conversion_map[col](row[col])


def get_device_table(csvpath):
    routes_path = csvpath.parent / csvpath.name.replace(".wpan.eth.csv.gz", ".routes.txt")
    device_table = {}
    with routes_path.open() as routes_file:
        reader = csv.DictReader(
            routes_file,
            delimiter=" ",
            fieldnames=["name", "ipv6", "eth"]
        )
        for row in reader:
            convert_columns(row, ROUTE_COL_TYPES)
            device_table[row["eth"]] = row["name"]
    return device_table


def get_rules(csvpath, device_table):
    schc_path = csvpath.parent / ".." / "scenarios" / "schc"
    rule_name = re.sub(r"^(.+-schc-[dp][12]).*", r"\1", csvpath.name)
    rule_mode = re.sub(r"^.+-schc-[dp][12](-([^_]+))?_.*", r"\2", csvpath.name)

    rev_device_table = {v: k for k, v in device_table.items()}

    if rule_mode == "min-rules":
        rules_paths = {
            rev_device_table["client"]: schc_path / f"{rule_name}-rules-min.json"
        }
    elif rule_mode == "peer-based":
        rules_paths = {}
        for rules in schc_path.glob(f"{rule_name}-rules-*.json"):
            if rules.name.endswith("-min.json"):
                continue
            else:
                host = re.sub(r".*-rules-(.*)\.json", r"\1", rules.name)
                host_addr = rev_device_table[host]
                client_addr = rev_device_table["client"]
                rules_paths[
                    bytes(a ^ b for a, b in zip(host_addr, client_addr))
                ] = rules
    else:
        rules_paths = {
            rev_device_table["client"]: schc_path / f"{rule_name}-rules.json"
        }

    for rules in rules_paths.values():
        assert rules.exists(), f"{rules} does not exist"
    return rules_paths



class DevNull:
    def __enter__(self):
        self._stdout = sys.stdout
        self._stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        return self

    def __exit__(self, *args):
        del sys.stdout
        del sys.stderr
        sys.stdout = self._stdout
        sys.stderr = self._stderr


def dump_pkt(pkt):
    chunk_size = 16
    for i in range(0, len(pkt), chunk_size):
        chunk = pkt[i:i+chunk_size]
        print(f"{i:06x}", binascii.hexlify(chunk, " ").decode())
    print(f"{len(pkt):06x}")


def read_csv(csvfile, device_table, rules):
    reader = csv.DictReader(csvfile, delimiter="\t")
    openschc_loader = OpenSCHCLoader(OPENSCHC_PATH)
    warnings.filterwarnings("ignore")

    rule_manager = openschc_loader.get_rule_manager()
    for device_id, rules_file in rules.items():
        rule_manager.Add(device=device_id, file=str(rules_file))
    peer_based = len(rules) > 1
    protocol = {}
    for key in device_table:
        protocol[key] = openschc_loader.get_protocol(
            layer2=unittest.mock.MagicMock(),
            system=unittest.mock.MagicMock(),
            role="device" if device_table[key] == "client" else "core",
        )
        protocol[key].set_rulemanager(rule_manager)
    fragment_rows = {k: [] for k in device_table}
    prev_frame_num = 0
    for i, row in enumerate(reader):
        convert_columns(row, ETH_COL_TYPES)

        assert row["frame.number"] == prev_frame_num + 1, (
            f"Unexpected frame number: {row['frame.number']} != {prev_frame_num + 1}"
        )
        prev_frame_num = row["frame.number"]
        if row["eth.type"] != 0x88b5:
            print(row["frame.time_epoch"])
            dump_pkt(row["eth.payload"])
            continue

        src = row["eth.src"]
        dst = row["eth.dst"]
        from_device = device_table[src] == "client"
        if from_device:
            kwargs = {"device_id": src, "core_id": dst}
        else:
            kwargs = {"device_id": dst, "core_id": src}
        if peer_based:
            kwargs["device_id"] = bytes(a ^ b for a, b in zip(src, dst))

        with DevNull():
            device_id, pkt = protocol[dst].schc_recv(row["eth.payload"], **kwargs)

        assert device_id

        if pkt is None:
            fragment_rows[dst].append((i, row))
        else:
            pkt = bytes(pkt)
            for j, fragment_row in fragment_rows[dst]:
                print(fragment_row["frame.time_epoch"])
                dump_pkt(pkt)
            print(row["frame.time_epoch"])
            dump_pkt(pkt)
            del fragment_rows[dst][:]
        protocol[dst].layer2.reset_mock()
        protocol[dst].system.reset_mock()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "eth_csv",
        help="A CSV containing SCHC encoded Ethernet payloads"
        r"with the following columns separated by tabs (`\t`). "
        "frame.number: The frame number from the original PCAP, "
        "frame.time_epoch: The time since UNIX epoch from the original PCAP, "
        "eth.src: The Ethernet source address in hexadecimal, "
        "eth.dst: The Ethernet destination address in hexadecimal, "
        "eth.type: The Ethertype used to mark SCHC frames in hexadecimal `0x` notation, "
        "eth.payload: The payload of the Ethernet frame in hexadecimal",
        type=pathlib.Path)
    args = parser.parse_args()

    device_table = get_device_table(args.eth_csv)
    rules = get_rules(args.eth_csv, device_table)
    with gzip.open(args.eth_csv, "rt") as csvfile:
        read_csv(csvfile, device_table, rules)


if __name__ == "__main__":
    main()
