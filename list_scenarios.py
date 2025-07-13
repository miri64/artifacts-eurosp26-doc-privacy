#! /usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

import argparse


PROTOCOLS = ["https", "coap", "coaps", "oscore", "oscore-base"]
LINK_LAYERS = ["", "-schc"]
LINK_LAYER_MODES = ["", "-min-rules", "-peer-based"]
BLOCKWISE = ["", "_b64"]
NETWORK_SETUPS = ["d1", "d2", "p1", "p2"]
DATA_FORMATS = ["json", "cbor"]
DNS_FORMATS = ["dns_message", "dns_cbor"]


def list_scenarios_full(filter_protocol=None, filter_data=None, filter_dns=None):
    for data in DATA_FORMATS:
        if filter_data is not None and data not in filter_data:
            continue
        for dns in DNS_FORMATS:
            if filter_dns is not None and dns not in filter_dns:
                continue
            for l2 in LINK_LAYERS:
                for l2_mode in LINK_LAYER_MODES:
                    if l2_mode and not l2:
                        continue
                    for prot in PROTOCOLS:
                        if prot == "coap" and l2:
                            continue
                        if filter_protocol is not None and prot not in filter_protocol:
                            continue
                        for blk in BLOCKWISE:
                            if prot == "https" and (blk or l2):
                                continue
                            for stp in NETWORK_SETUPS:
                                if l2_mode == "-min-rules":
                                    if not (
                                        stp == "d2"
                                        or (stp == "p2" and prot == "oscore-base")
                                    ):
                                        continue
                                if l2_mode == "-peer-based" and stp != "d2":
                                    continue
                                yield (
                                    f"{prot}{l2}-{stp}{l2_mode}_{data}_{dns}{blk}",
                                    prot,
                                    l2,
                                    stp,
                                    l2_mode,
                                    data,
                                    dns,
                                    blk,
                                )


def list_scenarios(filter_protocol=None, filter_data=None, filter_dns=None):
    for scenario, _, _, _, _, _, _, _ in list_scenarios_full(
        filter_protocol=filter_protocol,
        filter_data=filter_data,
        filter_dns=filter_dns,
    ):
        yield scenario


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p",
        "--protocol",
        help="Protocol to train for (default: all)",
        nargs="+",
        default=None,
        choices=PROTOCOLS,
    )
    parser.add_argument(
        "-D",
        "--data-formats",
        help="Data format to train for (default: all)",
        nargs="+",
        default=None,
        choices=DATA_FORMATS,
    )
    parser.add_argument(
        "-d",
        "--dns-formats",
        help="DNS format to train for (default: all)",
        nargs="+",
        default=None,
        choices=DNS_FORMATS,
    )
    args = parser.parse_args()
    for scenario in list_scenarios(
        args.protocol,
        args.data_formats,
        args.dns_formats,
    ):
        print(scenario)


if __name__ == "__main__":
    main()
