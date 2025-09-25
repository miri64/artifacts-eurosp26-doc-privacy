#! /usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

import argparse
import csv
import functools
import os
import pathlib
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
    PROTOCOLS,
    DATA_FORMATS,
    DNS_FORMATS,
    LINK_LAYERS,
    NETWORK_SETUPS,
)

try:
    if int(os.environ.get("FORCE_SKLEARN", "0")):
        raise ImportError(f"FORCE_SKLEARN={os.environ['FORCE_SKLEARN']}")
    from cuml import ensemble as sk_ensemble
    from cuml import linear_model as sk_linear_model
    from cuml import neighbors as sk_neighbors
    from cuml import preprocessing as sk_pp
    from cuml import svm as sk_svm
    import cuml
    using_cuml = True
except ImportError as exc:
    print("Unable to import cuML falling back to sklearn", file=sys.stderr)
    traceback.print_exc()

    # prevent OpenBLAS to crash when using sklearn's KNN
    os.environ['OPENBLAS_NUM_THREADS'] = "64"
    os.environ['MKL_NUM_THREADS'] = "64"
    os.environ['OMP_NUM_THREADS'] = "64"

    from sklearn import ensemble as sk_ensemble
    from sklearn.exceptions import ConvergenceWarning
    from sklearn import linear_model as sk_linear_model
    from sklearn import neighbors as sk_neighbors
    from sklearn import preprocessing as sk_pp
    from sklearn import svm as sk_svm
    using_cuml = False


from sklearn.ensemble import AdaBoostClassifier
from sklearn import model_selection as sk_model_selection
from sklearn import tree as sk_tree


EVALUATION_DIR = pathlib.Path.cwd()
INPUT_PATH = pathlib.Path(
    os.environ.get("INPUT_PATH", EVALUATION_DIR / "output_dataset")
)

K = 5
SCORINGS = [
    "accuracy",
    "precision",
    "recall",
    "f1",
    "balanced_accuracy",
    "roc_auc",
]

CLASSIFIERS = [
    "lr",
    "knn",
    # # Our datasets have >4.7 billion (> 2 * 120699 * 1219 * 16) samples for which SVM
    # # does not scale (not recommended for >1 million, 10-100k samples are best, see
    # # https://github.com/scikit-learn/scikit-learn/issues/18027#issuecomment-800873636
    # # ).For our particular datasets it crashes due to Int32 overflow error.
    # # We keep the code for smaller samples though.
    # "svm",
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
    "k",
    "classifier",
    "classifier_args",
    "job_id",
    "fit_time",
    "score_time",
    "accuracy",
    "precision",
    "recall",
    "f1_score",
    "balanced_accuracy",
    "roc_auc",
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
    "lr": "Logistic Regression",
    "knn": "K-Nearest Neighbors",
    "svm": "Support Vector Machine",
    "dt": "Decision Tree",
    "rf": "Random Forest (Ensemble Learning III)",
    "ab": "AdaBoost (SAMME)"
}
CLASSIFIER_ARGS = {
    "lr": {"max_iter": 2800},
    "knn": {
        "algorithm": "brute",
        "n_jobs": -1,
    },
    "svm": {"C": 0.01},
    "dt": {},
    "rf": {"n_estimators": 250, "max_depth": 9},
    "ab": {"n_estimators": 250},
}


def cross_validate(model, x, y):
    return sk_model_selection.cross_validate(
        model,
        x,
        y,
        cv=K,
        scoring=SCORINGS,
    )


def cross_validate_lr(x, y):
    lr = sk_linear_model.LogisticRegression(**CLASSIFIER_ARGS["lr"])
    try:
        return cross_validate(lr, x, y)
    finally:
        del lr


def cross_validate_knn(x, y):
    knn = sk_neighbors.KNeighborsClassifier(**CLASSIFIER_ARGS["knn"])
    try:
        return cross_validate(knn, x, y)
    finally:
        del knn


def cross_validate_svm(x, y):
    svm = sk_svm.LinearSVC(**CLASSIFIER_ARGS["svm"])
    try:
        return cross_validate(svm, x, y)
    finally:
        del svm


def cross_validate_dt(x, y):
    dt = sk_tree.DecisionTreeClassifier(**CLASSIFIER_ARGS["dt"])
    try:
        return cross_validate(dt, x, y)
    finally:
        del dt


def cross_validate_rf(x, y):
    rf = sk_ensemble.RandomForestClassifier(**CLASSIFIER_ARGS["rf"])
    try:
        return cross_validate(rf, x, y)
    finally:
        del rf


def cross_validate_ab(x, y):
    ab = AdaBoostClassifier(**CLASSIFIER_ARGS["ab"])
    try:
        return cross_validate(ab, x, y)
    finally:
        del ab


CROSS_VALIDITE = {
    "lr": cross_validate_lr,
    "knn": cross_validate_knn,
    "svm": cross_validate_svm,
    "dt": cross_validate_dt,
    "rf": cross_validate_rf,
    "ab": cross_validate_ab,
}


def str_classifier_args(classifier):
    args = ",".join(f"{k}={v}" for k, v in CLASSIFIER_ARGS[classifier].items())
    if args:
        return args
    return None


def configure_cuml():
    if using_cuml:
        CLASSIFIERS.insert(3, "svm")
        CLASSIFIER_ARGS["lr"]["max_iter"] = 5000
        del CLASSIFIER_ARGS["knn"]["n_jobs"]
        print("Using cuML")


def main():
    global CLASSIFIERS
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
    parser.add_argument(
        "-c",
        "--classifier",
        help="Classifier to use for training (default: all)",
        default=None,
        choices=CLASSIFIERS,
    )
    parser.add_argument(
        "-v",
        "--vector-type",
        help="Vector type to train for (default: \"binvec\")",
        default="binvec",
        choices=["binvec", "word2vec"],
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

    configure_cuml()
    if args.classifier is not None:
        if args.classifier not in CLASSIFIERS and args.classifier != "ab":
            raise ValueError(
                f"{args.classifier} not supported for your module configuration. "
                "(It might work with cuML.)"
            )
        CLASSIFIERS = [args.classifier]
    if "SLURM_JOB_ID" in os.environ:
        job_id = os.environ["SLURM_JOB_ID"]
    else:
        job_id = None
    start = time.time()
    for scenario, prot, l2, stp, l2_mode, data, dns, blk, randiv_pad in list_scenarios_full(
        args.protocol,
        args.data_formats,
        args.dns_formats,
        args.link_layer,
        args.network_setups,
    ):
        print(f"# {scenario}")
        sys.stdout.flush()
        file = INPUT_PATH / f"{scenario}.{args.vector_type}.parquet"
        if args.classifier is None:
            results_file = INPUT_PATH / f"{scenario}.{args.vector_type}.cross_val.csv"
        else:
            results_file = INPUT_PATH / f"{scenario}.{args.vector_type}.{args.classifier}.cross_val.csv"

        if results_file.exists():
            try:
                lf = polars.scan_csv(results_file, separator=";").with_columns(
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
                ) == set(
                    (c, str_classifier_args(c)) for c in CLASSIFIERS
                ):
                    print(
                        " - Skipping since results for all classifiers "
                        f"are in {results_file.relative_to(INPUT_PATH)}"
                    )
                    sys.stdout.flush()
                    continue
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
            with open(
                results_file, "w" if lf is None else "a"
            ) as csvfile:
                writer = csv.DictWriter(
                    csvfile, fieldnames=FIELD_NAMES, delimiter=";"
                )
                if lf is None:
                    writer.writeheader()
                    csvfile.flush()
                for cls in CLASSIFIERS:
                    print(f"## {CLASSIFIER_READABLE[cls]}")
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
                            & (polars.col("classifier") == cls)
                            & (
                                (
                                    polars.col("classifier_args")
                                    == str_classifier_args(cls)
                                )
                                if str_classifier_args(cls)
                                else polars.col("classifier_args").is_null()
                            )
                        ).collect().is_empty()
                    ):
                        print(
                            " - Skipping since it is already in",
                            results_file.relative_to(INPUT_PATH),
                        )
                        sys.stdout.flush()
                        continue
                    try:
                        score = CROSS_VALIDITE[cls](x_minmax, y)
                        sys.stderr.flush()
                        sys.stdout.flush()
                    except (ValueError, MemoryError):
                        print(f"# {scenario}", file=sys.stderr)
                        traceback.print_exc(file=sys.stderr)
                        sys.stderr.flush()
                        continue
                    writer.writerow(
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
                            "k": K,
                            "classifier": cls,
                            "classifier_args": str_classifier_args(
                                cls
                            ),
                            "job_id": job_id,
                            "fit_time": score["fit_time"].tolist(),
                            "score_time": score["score_time"].tolist(),
                            "accuracy": score["test_accuracy"].tolist(),
                            "precision": score["test_precision"].tolist(),
                            "recall": score["test_recall"].tolist(),
                            "f1_score": score["test_f1"].tolist(),
                            "balanced_accuracy": score["test_balanced_accuracy"].tolist(),
                            "roc_auc": score["test_roc_auc"].tolist(),
                        }
                    )
                    csvfile.flush()
        else:
            print(f"Skipping since {file} does not exist.")
            sys.stdout.flush()
    stop = time.time()
    print(f"# Duration {stop - start:.0f}\n")
    print(f"- start: {start:.03f}")
    print(f"- stop: {stop:.03f}")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
