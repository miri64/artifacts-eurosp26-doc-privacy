#! /usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

import argparse
import functools
import re


PROTOCOLS = ["https", "coap", "coaps", "oscore", "oscore-base"]
LINK_LAYERS = ["", "-schc"]
LINK_LAYER_MODES = ["", "-min-rules", "-peer-based"]
BLOCKWISE = ["", "_b64"]
NETWORK_SETUPS = ["d1", "d2", "p1", "p2"]
DATA_FORMATS = ["json", "cbor"]
DNS_FORMATS = ["dns_message", "dns_cbor"]
RANDIV_PAD = ["", "_randiv_pad"]

LINK_LAYER_READABLE = {
    "": "eth",
    "-schc": "schc",
}


def list_scenarios_full(
    filter_protocol=None,
    filter_data=None,
    filter_dns=None,
    filter_link_layer=None,
    filter_network_setup=None,
    filter_randiv_pad=False,
):
    for data in DATA_FORMATS:
        if filter_data is not None and data not in filter_data:
            continue
        for dns in DNS_FORMATS:
            if filter_dns is not None and dns not in filter_dns:
                continue
            for l2 in LINK_LAYERS:
                if filter_link_layer is not None and l2 not in filter_link_layer:
                    continue
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
                                if (
                                    filter_network_setup is not None
                                    and stp not in filter_network_setup
                                ):
                                    continue
                                if l2_mode == "-min-rules":
                                    if not (
                                        stp == "d2"
                                        or (stp == "p2" and prot == "oscore-base")
                                    ):
                                        continue
                                if l2_mode == "-peer-based" and stp != "d2":
                                    continue
                                for ri_pad in RANDIV_PAD:
                                    if ri_pad and prot not in ["coaps", "oscore"]:
                                        continue
                                    if filter_randiv_pad and ri_pad:
                                        continue
                                    yield (
                                        f"{prot}{l2}-{stp}{l2_mode}_{data}_{dns}{blk}{ri_pad}",
                                        prot,
                                        l2,
                                        stp,
                                        l2_mode,
                                        data,
                                        dns,
                                        blk,
                                        ri_pad,
                                    )


def list_scenarios(
    filter_protocol=None,
    filter_data=None,
    filter_dns=None,
    filter_link_layer=None,
    filter_network_setup=None,
    filter_randiv_pad=False,
):
    for scenario, _, _, _, _, _, _, _, _ in list_scenarios_full(
        filter_protocol=filter_protocol,
        filter_data=filter_data,
        filter_dns=filter_dns,
        filter_link_layer=filter_link_layer,
        filter_network_setup=filter_network_setup,
        filter_randiv_pad=filter_randiv_pad,
    ):
        yield scenario


def parse_scenario_name(scenario):
    """
    >>> parse_scenario_name("")
    Traceback (most recent call last):
    ...
    ValueError: Not a valid scenario name
    >>> as_exp = 0
    >>> for scenario, *exp in list_scenarios_full():
    ...     if parse_scenario_name(scenario) == tuple(exp):
    ...         as_exp += 1
    ...     else:
    ...         print(f"Not as expected: {scenario}")
    ...         print(f"  Exp: {tuple(exp)})")
    ...         print(f"  Got: {parse_scenario_name(scenario)}")
    >>> as_exp
    456
    """
    match = re.match(
        f"^({'|'.join(PROTOCOLS)})"
        f"({'|'.join(LINK_LAYERS)})"
        f"-({'|'.join(NETWORK_SETUPS)})"
        f"({'|'.join(LINK_LAYER_MODES)})"
        f"_({'|'.join(DATA_FORMATS)})"
        f"_({'|'.join(DNS_FORMATS)})"
        f"({'|'.join(BLOCKWISE)})"
        f"({'|'.join(RANDIV_PAD)})$",
        scenario,
    )

    if match is None:
        raise ValueError("Not a valid scenario name")
    return match.groups()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p",
        "--protocol",
        help="Protocol to train for (default: all)",
        nargs="+",
        action="append",
        default=None,
        choices=PROTOCOLS,
    )
    parser.add_argument(
        "-D",
        "--data-formats",
        help="Data format to train for (default: all)",
        nargs="+",
        action="append",
        default=None,
        choices=DATA_FORMATS,
    )
    parser.add_argument(
        "-d",
        "--dns-formats",
        help="DNS format to train for (default: all)",
        nargs="+",
        action="append",
        default=None,
        choices=DNS_FORMATS,
    )
    parser.add_argument(
        "-l",
        "--link-layer",
        help="Link layer to train for (default: all)",
        nargs="+",
        action="append",
        default=None,
        choices=LINK_LAYER_READABLE.values(),
    )
    parser.add_argument(
        "-n",
        "--network-setups",
        help="Network setup to train for (default: all)",
        nargs="+",
        action="append",
        default=None,
        choices=NETWORK_SETUPS,
    )
    args = parser.parse_args()

    if args.network_setups is not None:
        args.network_setups = list(functools.reduce(lambda x, y: x + y, args.network_setups, []))
    if args.protocol is not None:
        args.protocol = list(functools.reduce(lambda x, y: x + y, args.protocol, []))
    if args.data_formats is not None:
        args.data_formats = list(functools.reduce(lambda x, y: x + y, args.data_formats, []))
    if args.dns_formats is not None:
        args.dns_formats = list(functools.reduce(lambda x, y: x + y, args.dns_formats, []))
    if args.link_layer is not None:
        args.link_layer = list(functools.reduce(lambda x, y: x + y, args.link_layer, []))
        args.link_layer = [
            {v: k for k, v in LINK_LAYER_READABLE.items()}[l]
            for l in args.link_layer
        ]

    for scenario in list_scenarios(
        args.protocol,
        args.data_formats,
        args.dns_formats,
        args.link_layer,
        args.network_setups,
    ):
        print(scenario)


if __name__ == "__main__":
    main()
