#! /usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

import argparse
import csv
import os
import pathlib
import psutil
import sys
import time
import traceback
import warnings

import numpy
import polars
import polars.exceptions

EVALUATION_PATH = pathlib.Path(__file__).resolve().parent
INPUT_PATH = pathlib.Path(
    os.environ.get("INPUT_PATH", EVALUATION_PATH / ".." / "output_dataset")
)
BASE_DIR = (EVALUATION_PATH / "..").absolute()

if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from list_scenarios import (
    parse_scenario_name,
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
    "svm",
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


CROSS_VALIDATE = {
    "lr": cross_validate_lr,
    "knn": cross_validate_knn,
    "svm": cross_validate_svm,
    "dt": cross_validate_dt,
    "rf": cross_validate_rf,
    "ab": cross_validate_ab,
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


def configure_cuml():
    sklearn = __import__("sklearn")
    globals()["AdaBoostClassifier"] = sklearn.ensemble.AdaBoostClassifier

    try:
        if int(os.environ.get("FORCE_SKLEARN", "0")):
            raise ImportError(f"FORCE_SKLEARN={os.environ['FORCE_SKLEARN']}")

        cuml = __import__("cuml")
        globals()["cuml"] = cuml
        globals()["sk_ensemble"] = cuml.ensemble
        globals()["sk_linear_model"] = cuml.linear_model
        globals()["sk_neighbors"] = cuml.neighbors
        globals()["sk_pp"] = cuml.preprocessing
        globals()["sk_svm"] = cuml.svm
        using_cuml = True
    except ImportError as exc:
        print("Unable to import cuML falling back to sklearn", file=sys.stderr)
        traceback.print_exc()

        # prevent OpenBLAS to crash when using sklearn's KNN
        os.environ['OPENBLAS_NUM_THREADS'] = "64"
        os.environ['MKL_NUM_THREADS'] = "64"
        os.environ['OMP_NUM_THREADS'] = "64"

        globals()["sk_ensemble"] = sklearn.ensemble
        globals()["ConvergenceWarning"] = sklearn.exceptions.ConvergenceWarning
        globals()["sk_linear_model"] = sklearn.linear_model
        globals()["sk_neighbors"] = sklearn.neighbors
        globals()["sk_pp"] = sklearn.preprocessing
        globals()["sk_svm"] = sklearn.svm
        using_cuml = False

    globals()["sk_model_selection"] = sklearn.model_selection
    globals()["sk_tree"] = sklearn.tree

    if using_cuml:
        CLASSIFIER_ARGS["svm"]["output_type"] = "numpy"
        CLASSIFIER_ARGS["rf"]["output_type"] = "numpy"
        CLASSIFIER_ARGS["lr"]["max_iter"] = 5000
        del CLASSIFIER_ARGS["knn"]["n_jobs"]
        print("Using cuML")


def main():
    global CLASSIFIERS
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-v",
        "--vector-type",
        help="Vector type to train for (default: \"binvec\")",
        default="binvec",
        choices=["binvec", "word2vec"],
    )
    parser.add_argument(
        "scenario",
        help="Scenario name for scenario to evaluate",
    )
    parser.add_argument(
        "classifier",
        help="Classifier to use for evaluation",
        choices=CLASSIFIERS,
    )
    args = parser.parse_args()

    print(f"# {args.scenario}")
    sys.stdout.flush()

    configure_cuml()
    if "SLURM_JOB_ID" in os.environ:
        job_id = os.environ["SLURM_JOB_ID"]
    else:
        job_id = None
    start = time.time()
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

    file = INPUT_PATH / f"{args.scenario}.{args.vector_type}.parquet"
    results_file = INPUT_PATH / f"{args.scenario}.{args.vector_type}.{args.classifier}.cross_val.csv"

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
                return 128
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
                    return 0
                try:
                    try:
                        mem_before = process_memory()
                        score = CROSS_VALIDATE[args.classifier](x_minmax, y)
                    finally:
                        mem_after = process_memory()
                        print(f" - Memory: {mem_before} => {mem_after}")
                        sys.stderr.flush()
                        sys.stdout.flush()
                except (ValueError, MemoryError):
                    print(f"# {args.scenario}", file=sys.stderr)
                    traceback.print_exc(file=sys.stderr)
                    sys.stderr.flush()
                    return 0
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
                        "classifier": args.classifier,
                        "classifier_args": str_classifier_args(
                            args.classifier
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
                del score
        finally:
            del x_minmax
            del y
    else:
        print(f"Skipping since {file} does not exist.")
        sys.stdout.flush()
    stop = time.time()
    print(f"# Duration {stop - start:.0f}\n")
    print(f"- start: {start:.03f}")
    print(f"- stop: {stop:.03f}")
    sys.stdout.flush()


if __name__ == "__main__":
    sys.exit(main())
