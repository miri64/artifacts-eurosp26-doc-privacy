#! /usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

import argparse
import contextlib
import csv
import functools
import os
import pathlib
import psutil
import multiprocessing
import sys
import time
import traceback
import warnings

import numpy
import polars
import polars.exceptions

from list_scenarios import (
    list_scenarios_full,
    parse_scenario_name,
)


# cuML does not support the feature_importance_ attribute
# even with cuml.accel:
# - https://docs.rapids.ai/api/cuml/stable/cuml-accel/limitations/#randomforestclassifier
from sklearn import ensemble as sk_ensemble
from sklearn import model_selection as sk_model_selection
from sklearn import preprocessing as sk_pp
from sklearn import tree as sk_tree


EVALUATION_DIR = pathlib.Path.cwd()
INPUT_PATH = pathlib.Path(
    os.environ.get("INPUT_PATH", EVALUATION_DIR / "output_dataset")
)

CLASSIFIERS = [
    "dt",
    "rf",
    "ab",
]
FIELD_NAMES = [
    "protocol",
    "link_layer",
    "link_layer_mode",
    "blocksize",
    "network_setup",
    "data_format",
    "dns_format",
    "randiv_pad",
    "vector_type",
    "classifier",
    "classifier_args",
    "job_id",
    "start",
    "stop",
    "feature",
    "mdi",
    "mdi_std",
]

LINK_LAYER_READABLE = {
    "": "eth",
    "-schc": "schc",
}
LINK_LAYER_MODE_READABLE = {
    "": "",
    "-min-rules": "min_rules",
    "-peer-based": "peer_based",
}
BLOCKWISE_READABLE = {
    "": "1024",
    "_b64": "64",
}

CLASSIFIER_READABLE = {
    "dt": "Decision Tree",
    "rf": "Random Forest (Ensemble Learning III)",
    "ab": "AdaBoost (SAMME)"
}

RANDOM_SEED = 0x61596c9b

CLASSIFIER_ARGS = {
    "dt": {"random_state": RANDOM_SEED},
    "rf": {
        "n_estimators": 250,
        "max_depth": 9,
        "random_state": RANDOM_SEED,
    },
    "ab": {
        "n_estimators": 250,
        "random_state": RANDOM_SEED,
    },
}


@contextlib.contextmanager
def fit_dt(x, y):
    dt = sk_tree.DecisionTreeClassifier(**CLASSIFIER_ARGS["dt"])
    dt.fit(x, y)
    try:
        yield dt
    finally:
        del dt


@contextlib.contextmanager
def fit_rf(x, y):
    rf = sk_ensemble.RandomForestClassifier(**CLASSIFIER_ARGS["rf"])
    rf.fit(x, y)
    try:
        yield rf
    finally:
        del rf


@contextlib.contextmanager
def fit_ab(x, y):
    ab = sk_ensemble.AdaBoostClassifier(**CLASSIFIER_ARGS["ab"])
    ab.fit(x, y)
    try:
        yield ab
    finally:
        del ab


FIT = {
    "dt": fit_dt,
    "rf": fit_rf,
    "ab": fit_ab,
}


def process_memory():
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    return mem_info.rss


def str_classifier_args(classifier):
    args = ",".join(
        f"{k}={v}"
        for k, v
        in CLASSIFIER_ARGS[classifier].items()
        if k != "output_type"
    )
    if args:
        return args
    return None


def main():
    global CLASSIFIERS
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--classifier",
        help="Classifier to use",
        default="rf",
        choices=CLASSIFIERS,
    )
    parser.add_argument(
        "-v",
        "--vector-type",
        help="Vector type to train for (default: \"binvec\")",
        default="binvec",
        choices=["binvec", "word2vec"],
    )
    parser.add_argument(
        "scenario",
        help="Scenario name for scenario to evaluate"
    )
    args = parser.parse_args()

    if "SLURM_JOB_ID" in os.environ:
        job_id = os.environ["SLURM_JOB_ID"]
    else:
        job_id = None

    print(f"# {args.scenario}")
    sys.stdout.flush()
    file = INPUT_PATH / f"{args.scenario}.{args.vector_type}.parquet"
    results_file = INPUT_PATH / (
        f"{args.scenario}.{args.vector_type}.{args.classifier}.feat_imp.csv"
    )
    (
        prot,
        l2,
        stp,
        l2_mode,
        data,
        dns,
        blk,
        randiv_pad,
    ) = parse_scenario_name(args.scenario)

    if results_file.exists():
        try:
            lf = polars.scan_csv(
                results_file,
                schema_overrides={
                    "blocksize": polars.Int16,
                    "network_setup": polars.String,
                    "randiv_pad": polars.Int8,
                },
                separator=";",
            ).with_columns(
                (polars.col("link_layer_mode")).fill_null("")
            )
            if set(
                tuple(d.values())
                for d in lf.filter(
                    (polars.col("protocol") == prot)
                    & (polars.col("link_layer") == LINK_LAYER_READABLE[l2])
                    & (polars.col("link_layer_mode") == LINK_LAYER_MODE_READABLE[l2_mode])
                    & (polars.col("blocksize") == int(BLOCKWISE_READABLE[blk]))
                    & (polars.col("network_setup") == stp)
                    & (polars.col("data_format") == data)
                    & (polars.col("dns_format") == dns)
                    & (polars.col("randiv_pad") == int(randiv_pad != ""))
                    & (polars.col("vector_type") == args.vector_type)
                ).select(["classifier", "classifier_args"]).collect().to_dicts()
            ) >= set(  # is superset
                (c, str_classifier_args(c)) for c in CLASSIFIERS
            ):
                print(
                    " - Skipping since results for all classifiers "
                    f"are in {results_file.relative_to(INPUT_PATH)}"
                )
                sys.stdout.flush()
                return
        except polars.exceptions.NoDataError:
            lf = None
    else:
        lf = None

    if file.exists():
        lf_vec = polars.scan_parquet(file)
        max_length = lf_vec.select("vector").with_columns(
            polars.col("vector").list.len()
        ).max().collect().item()
        df_vec = lf_vec.cast(
            {
                "vector": polars.Array(
                    polars.Int8
                    if args.vector_type == "binvec"
                    else polars.Float32,
                    max_length,
                )
            }
        ).select("vector", "label").collect()
        x = df_vec["vector"].to_numpy()
        y = df_vec["label"].to_numpy()
        del df_vec
        del lf_vec
        scaler = sk_pp.MinMaxScaler()
        x_minmax = scaler.fit_transform(x)
        del x
        try:
            with open(
                results_file, "w" if lf is None else "a"
            ) as csvfile:
                writer = csv.DictWriter(
                    csvfile, fieldnames=FIELD_NAMES, delimiter=";"
                )
                if lf is None:
                    writer.writeheader()
                    csvfile.flush()
                print(f"## {CLASSIFIER_READABLE[args.classifier]}")
                sys.stdout.flush()
                if (
                    lf is not None
                    and not lf.filter(
                        (polars.col("protocol") == prot)
                        & (
                            polars.col("link_layer")
                            == LINK_LAYER_READABLE[l2]
                        )
                        & (
                            polars.col("link_layer_mode")
                            == LINK_LAYER_MODE_READABLE[l2_mode]
                        )
                        & (
                            polars.col("blocksize")
                            == int(BLOCKWISE_READABLE[blk])
                        )
                        & (polars.col("network_setup") == stp)
                        & (polars.col("data_format") == data)
                        & (polars.col("dns_format") == dns)
                        & (polars.col("randiv_pad") == int(randiv_pad != ""))
                        & (polars.col("vector_type") == args.vector_type)
                        & (polars.col("classifier") == args.classifier)
                        & (
                            (
                                polars.col("classifier_args")
                                == str_classifier_args(args.classifier)
                            )
                            if str_classifier_args(args.classifier)
                            else polars.col("classifier_args").is_null()
                        )
                    ).collect().is_empty()
                ):
                    print(
                        " - Skipping since it is already in",
                        results_file.relative_to(INPUT_PATH),
                    )
                    sys.stdout.flush()
                    return
                try:
                    mem_before = process_memory()
                    start = int(time.time())
                    importances = []
                    importances_std = []
                    try:
                        with FIT[args.classifier](x_minmax, y) as model:
                            importances = model.feature_importances_
                            # if classifier is an ensemble clssifier
                            if args.classifier in ["ab", "rf"]:
                                importances_std = numpy.std(
                                    [
                                        tree.feature_importances_
                                        for tree in model.estimators_
                                    ],
                                    axis=0,
                                )
                            else:
                                importances_std = [None for _ in importances]
                    finally:
                        stop = int(time.time())
                        mem_after = process_memory()
                        print(f" - Memory: {mem_before} => {mem_after}")
                        sys.stderr.flush()
                        sys.stdout.flush()
                except (ValueError, MemoryError):
                    print(f"# {args.scenario}", file=sys.stderr)
                    traceback.print_exc(file=sys.stderr)
                    sys.stderr.flush()
                    return
                writer.writerows(
                    [
                        {
                            "protocol": prot,
                            "link_layer": LINK_LAYER_READABLE[l2],
                            "link_layer_mode": LINK_LAYER_MODE_READABLE[l2_mode],
                            "blocksize": int(BLOCKWISE_READABLE[blk]),
                            "network_setup": stp,
                            "data_format": data,
                            "dns_format": dns,
                            "randiv_pad": int(randiv_pad != ""),
                            "vector_type": args.vector_type,
                            "classifier": args.classifier,
                            "classifier_args": str_classifier_args(
                                args.classifier
                            ),
                            "job_id": job_id,
                            "start": start,
                            "stop": stop,
                            "feature": f,
                            "mdi": mdi,
                            "mdi_std": mdi_std,
                        }
                        for f, (mdi, mdi_std) in enumerate(
                            zip(importances, importances_std)
                        )
                    ]
                )
                csvfile.flush()
                del importances
                del importances_std
        finally:
            del x_minmax
            del y
    else:
        print(f"Skipping since {file} does not exist.")
        sys.stdout.flush()
    sys.stdout.flush()


if __name__ == "__main__":
    main()
