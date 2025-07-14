#! /usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

import argparse
import csv
import functools
import sys
import traceback

import polars

from list_scenarios import (
    list_scenarios_full,
    PROTOCOLS,
    DATA_FORMATS,
    DNS_FORMATS,
    LINK_LAYERS,
)
from training import (
    CLASSIFIERS,
    LINK_LAYER_READABLE,
    LINK_LAYER_MODE_READABLE,
    BLOCKWISE_READABLE,
    INPUT_PATH,
    TEST_SIZE,
    TRAIN,
    configure_cuml,
    sk_model_selection,
    sk_pp,
    str_classifier_args,
    test,
)


FIELD_NAMES = [
    "protocol",
    "link_layer",
    "link_layer_mode",
    "blocksize",
    "network_setup",
    "data_format",
    "dns_format",
    "vector_type",
    "run",
    "test_size",
    "classifier",
    "classifier_args",
    "length",
    "max_length",
    "true_dns",
    "false_dns",
    "false_data",
    "true_data",
    "accuracy",
    "precision",
    "recall",
    "f1_score",
]


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
        "-c",
        "--classifier",
        help="Classifier to use for training (default: \"dt\")",
        default="dt",
        choices=TRAIN.keys(),
    )
    parser.add_argument(
        "-v",
        "--vector-type",
        help="Vector type to train for (default: \"binvec\")",
        default="binvec",
        choices=["binvec", "word2vec"],
    )
    parser.add_argument(
        "-r",
        "--run",
        help="Run this training counts for",
        type=int,
        default=1
    )
    parser.add_argument(
        "-s",
        "--step",
        help="Length increment for the ablation test",
        type=int,
        default=8,
    )
    args = parser.parse_args()

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
    configure_cuml()
    if args.classifier not in CLASSIFIERS:
        raise ValueError(
            f"{args.classifier} not supported for your module configuration. "
            "(It might work with cuML.)"
        )
    import pprint
    pprint.pp(
        list(
            list_scenarios_full(
                args.protocol, args.data_formats, args.dns_formats, args.link_layer
            )
        )
    )
    for scenario, prot, l2, stp, l2_mode, data, dns, blk in list_scenarios_full(
        args.protocol, args.data_formats, args.dns_formats, args.link_layer,
    ):
        step = args.step if not l2 else 1
        print(f"# {scenario}")
        file = INPUT_PATH / f"{scenario}.{args.vector_type}.parquet"
        results_file = INPUT_PATH / f"{scenario}.{args.vector_type}.ablation.csv"

        lf = None
        if not file.exists():
            print(f"Skipping since {file} does not exist.")
            continue
        if results_file.exists():
            lf = polars.scan_csv(results_file).with_columns(
                (polars.col("link_layer_mode")).fill_null("")
            )
            try:
                max_lengths = lf.select("max_length").collect()
                if not max_lengths.is_empty():
                    max_length = max_lengths["max_length"].last()
                    if sorted(
                        i[0]
                        for i in lf.filter(
                            (polars.col("protocol") == prot)
                            & (polars.col("link_layer") == LINK_LAYER_READABLE[l2])
                            & (
                                polars.col("link_layer_mode")
                                == LINK_LAYER_MODE_READABLE[l2_mode]
                            )
                            & (polars.col("blocksize") == int(BLOCKWISE_READABLE[blk]))
                            & (polars.col("network_setup") == stp)
                            & (polars.col("data_format") == data)
                            & (polars.col("dns_format") == dns)
                            & (polars.col("vector_type") == args.vector_type)
                            & (polars.col("run") == args.run)
                            & (polars.col("test_size") == TEST_SIZE)
                            & (polars.col("classifier") == args.classifier)
                            & (
                                (
                                    polars.col("classifier_args")
                                    == str_classifier_args(args.classifier)
                                )
                                if str_classifier_args(args.classifier) is not None
                                else polars.col("classifier_args").is_null()
                            )
                        ).select(
                            ["length"]
                        ).collect()[["length"]].rows()
                    ) == range(step, max_length + step, step):
                        print(
                            f" - Skipping since lengths with {args.classifier} "
                            f"are in {results_file.relative_to(INPUT_PATH)}"
                        )
                        continue
                del max_lengths
            except polars.exceptions.NoDataError:
                lf = None
        lf_vec = polars.scan_parquet(file)

        max_length = lf_vec.select("vector").with_columns(
            polars.col("vector").list.len()
        ).max().collect().item()
        with open(
            results_file, "w" if lf is None else "a"
        ) as csvfile:
            writer = csv.DictWriter(
                csvfile, fieldnames=FIELD_NAMES
            )
            if lf is None:
                writer.writeheader()
            for length in range(step, max_length + step, step):
                if lf is not None and lf.filter(
                    (polars.col("protocol") == prot)
                    & (polars.col("link_layer") == LINK_LAYER_READABLE[l2])
                    & (polars.col("link_layer_mode") == LINK_LAYER_MODE_READABLE[l2_mode])
                    & (polars.col("blocksize") == int(BLOCKWISE_READABLE[blk]))
                    & (polars.col("network_setup") == stp)
                    & (polars.col("data_format") == data)
                    & (polars.col("dns_format") == dns)
                    & (polars.col("vector_type") == args.vector_type)
                    & (polars.col("run") == args.run)
                    & (polars.col("test_size") == TEST_SIZE)
                    & (polars.col("classifier") == args.classifier)
                    & (
                        (
                            polars.col("classifier_args")
                            == str_classifier_args(args.classifier)
                        )
                        if str_classifier_args(args.classifier) is not None
                        else polars.col("classifier_args").is_null()
                    )
                    & (polars.col("length") == length)
                ).select(
                    ["length"]
                ).count().with_columns(
                    polars.col("length") > 0
                ).collect().item():
                    print(
                        f" - Skipping since {length} is already in",
                        results_file.relative_to(INPUT_PATH),
                    )
                    continue
                df_vec = lf_vec.with_columns(
                    polars.col("vector").list.slice(0, length)
                ).cast(
                    {
                        "vector": polars.Array(
                            polars.Int8
                            if args.vector_type == "binvec"
                            else polars.Float32,
                            length
                        ),
                    }
                ).select("vector", "label").collect()
                x = df_vec["vector"].to_numpy()
                y = df_vec["label"].to_numpy()
                del df_vec
                try:
                    x_train, x_test, y_train, y_test = (
                        sk_model_selection.train_test_split(
                            x, y, test_size=TEST_SIZE
                        )
                    )
                except MemoryError:
                    print(f"# {scenario}", file=sys.stderr)
                    del x
                    del y
                    traceback.print_exc(file=sys.stderr)
                    continue
                del x
                del y
                scaler = sk_pp.MinMaxScaler()
                x_train_minmax = scaler.fit_transform(x_train)
                x_test_minmax = scaler.transform(x_test)
                del x_train
                del x_test
                try:
                    with TRAIN[args.classifier](
                        x_train_minmax, y_train
                    ) as classifier:
                        (
                            conf_matrix,
                            accuracy,
                            precision,
                            recall,
                            f1score,
                        ) = test(classifier, x_test_minmax, y_test)
                except (ValueError, MemoryError):
                    print(f"# {scenario}", file=sys.stderr)
                    traceback.print_exc(file=sys.stderr)
                    continue
                writer.writerow(
                    {
                        "protocol": prot,
                        "link_layer": LINK_LAYER_READABLE[l2],
                        "link_layer_mode": LINK_LAYER_MODE_READABLE[l2_mode],
                        "blocksize": BLOCKWISE_READABLE[blk],
                        "network_setup": stp,
                        "data_format": data,
                        "dns_format": dns,
                        "vector_type": args.vector_type,
                        "run": args.run,
                        "test_size": TEST_SIZE,
                        "classifier": args.classifier,
                        "classifier_args": str_classifier_args(
                            args.classifier
                        ),
                        "length": length,
                        "max_length": max_length,
                        "true_data": conf_matrix[0][0],
                        "false_data": conf_matrix[0][1],
                        "false_dns": conf_matrix[1][0],
                        "true_dns": conf_matrix[1][1],
                        "accuracy": accuracy,
                        "precision": precision,
                        "recall": recall,
                        "f1_score": f1score,
                    }
                )
                csvfile.flush()
                del conf_matrix
                del x_train_minmax
                del x_test_minmax
                del y_train
                del y_test
        del lf_vec


if __name__ == "__main__":
    main()
