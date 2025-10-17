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
import itertools
import os
import numbers
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

import sklearn.inspection._permutation_importance as sk_perm_imp


EVALUATION_DIR = pathlib.Path.cwd()
INPUT_PATH = pathlib.Path(
    os.environ.get("INPUT_PATH", EVALUATION_DIR / "output_dataset")
)

TEST_SIZE = 0.2
REPEATS = 2
SCORINGS = [
    "accuracy",
    # "precision",
    # "recall",
    "f1",
    # "balanced_accuracy",
    # "roc_auc",
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
    "classifier",
    "classifier_args",
    "repeats",
    "job_id",
    "start",
    "stop",
    "feature",
    "accuracy_mean",
    "accuracy_std",
    "precision_mean",
    "precision_std",
    "recall_mean",
    "recall_std",
    "f1_mean",
    "f1_std",
    "balanced_accuracy_mean",
    "balanced_accuracy_std",
    "roc_auc_mean",
    "roc_auc_std",
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

RANDOM_SEED = 0x61596c9b

CLASSIFIER_ARGS = {
    "lr": {"max_iter": 2800, "random_state": RANDOM_SEED},
    "knn": {
        "algorithm": "brute",
        "n_jobs": -1,
    },
    "dt": {"random_state": RANDOM_SEED},
    "svm": {"C": 0.01, "random_state": RANDOM_SEED},
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
def fit_lr(x, y):
    lr = sk_linear_model.LogisticRegression(**CLASSIFIER_ARGS["lr"])
    lr.fit(x, y)
    try:
        yield lr
    finally:
        del lr


@contextlib.contextmanager
def fit_knn(x, y):
    knn = sk_neighbors.KNeighborsClassifier(**CLASSIFIER_ARGS["knn"])
    knn.fit(x, y)
    try:
        yield knn
    finally:
        del knn


@contextlib.contextmanager
def fit_svm(x, y):
    svm = sk_svm.LinearSVC(**CLASSIFIER_ARGS["svm"])
    svm.fit(x, y)
    try:
        yield svm
    finally:
        del svm


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
    "lr": fit_lr,
    "knn": fit_knn,
    "svm": fit_svm,
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


@sk_perm_imp.validate_params(
    {
        "estimator": [sk_perm_imp.HasMethods(["fit"])],
        "X": ["array-like"],
        "y": ["array-like", None],
        "scoring": [
            sk_perm_imp.StrOptions(set(sk_perm_imp.get_scorer_names())),
            callable,
            list,
            tuple,
            dict,
            None,
        ],
        "n_repeats": [
            sk_perm_imp.Interval(sk_perm_imp.Integral, 1, None, closed="left")
        ],
        "random_state": ["random_state"],
        "sample_weight": ["array-like", None],
        "max_samples": [
            sk_perm_imp.Interval(sk_perm_imp.Integral, 1, None, closed="left"),
            sk_perm_imp.Interval(sk_perm_imp.RealNotInt, 0, 1, closed="right"),
        ],
    },
    prefer_skip_nested_validation=True,
)
def permutation_importance(
    estimator,
    X,
    y,
    *,
    scoring=None,
    n_repeats=1,
    random_state=None,
    sample_weight=None,
    max_samples=1.0,
    slice_bytes=True,
):
    """
    Except for using slice for col_idx to permute over whole bytes for eth scenarios
    and not using Parallel + delayed due to memory constraints,
    this is a 1:1 copy of
    https://github.com/scikit-learn/scikit-learn/blob/bde39c1afc8/sklearn/inspection/_permutation_importance.py#L114C1-L313
    """
    random_state = sk_perm_imp.check_random_state(random_state)
    random_seed = random_state.randint(numpy.iinfo(numpy.int32).max + 1)

    if not isinstance(max_samples, numbers.Integral):
        max_samples = int(max_samples * X.shape[0])
    elif max_samples > X.shape[0]:
        raise ValueError("max_samples must be <= n_samples")

    scorer = sk_perm_imp.check_scoring(estimator, scoring=scoring)
    baseline_score = sk_perm_imp._weights_scorer(scorer, estimator, X, y, sample_weight)

    if slice_bytes:
        scores = [
            sk_perm_imp._calculate_permutation_scores(
                estimator,
                X,
                y,
                sample_weight,
                slice(col_idx, col_idx + 8),
                random_seed,
                n_repeats,
                scorer,
                max_samples,
            )
            for col_idx in range(0, X.shape[1], 8)
        ]
        # fill to original size of X.shape[1]
        scores = list(itertools.chain.from_iterable([[s] * 8 for s in scores]))
    else:
        scores = [
            sk_perm_imp._calculate_permutation_scores(
                estimator,
                X,
                y,
                sample_weight,
                col_idx,
                random_seed,
                n_repeats,
                scorer,
                max_samples,
            )
            for col_idx in range(X.shape[1])
        ]

    if isinstance(baseline_score, dict):
        return {
            name: sk_perm_imp._create_importances_bunch(
                baseline_score[name],
                # unpack the permuted scores
                numpy.array([scores[col_idx][name] for col_idx in range(X.shape[1])]),
            )
            for name in baseline_score
        }
    else:
        return sk_perm_imp._create_importances_bunch(
            baseline_score,
            numpy.array(scores)
        )


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
        "-R",
        "--repeats",
        help=f"Repeats of permutation (default: {REPEATS})",
        default=REPEATS,
        type=int,
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

    print(f"# {args.scenario}")
    sys.stdout.flush()

    if "SLURM_JOB_ID" in os.environ:
        job_id = os.environ["SLURM_JOB_ID"]
    else:
        job_id = None

    file = INPUT_PATH / f"{args.scenario}.{args.vector_type}.parquet"
    results_file = INPUT_PATH / (
        f"{args.scenario}.{args.vector_type}.{args.classifier}.perm_imp.csv"
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
        configure_cuml()
        scaler = sk_pp.MinMaxScaler()
        x_minmax = scaler.fit_transform(x)
        del x
        try:
            x_train, x_test, y_train, y_test = (
                sk_model_selection.train_test_split(
                    x_minmax, y, test_size=TEST_SIZE
                )
            )
        except MemoryError:
            print(f"# {scenario}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return
        del x_minmax
        del y
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
                        & (polars.col("repeats") == REPEATS)
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
                    try:
                        with FIT[args.classifier](x_train, y_train) as model:
                            result = permutation_importance(
                                model,
                                x_test,
                                y_test,
                                n_repeats=REPEATS,
                                random_state=RANDOM_SEED,
                                scoring=SCORINGS,
                                slice_bytes=not l2,
                            )
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
                        dict(
                            [
                                ("protocol", prot),
                                ("link_layer", LINK_LAYER_READABLE[l2]),
                                ("link_layer_mode", LINK_LAYER_MODE_READABLE[l2_mode]),
                                ("blocksize", int(BLOCKWISE_READABLE[blk])),
                                ("network_setup", stp),
                                ("data_format", data),
                                ("dns_format", dns),
                                ("randiv_pad", int(randiv_pad != "")),
                                ("vector_type", args.vector_type),
                                ("classifier", args.classifier),
                                (
                                    "classifier_args",
                                    str_classifier_args(
                                        args.classifier
                                    )
                                ),
                                ("repeats", REPEATS),
                                ("job_id", job_id),
                                ("start", start),
                                ("stop", stop),
                                ("feature", f),
                            ] + [
                                (
                                    f"{scoring}_mean",
                                    result[scoring].importances_mean[f]
                                )
                                for scoring in SCORINGS
                            ] + [
                                (
                                    f"{scoring}_std",
                                    result[scoring].importances_std[f]
                                )
                                for scoring in SCORINGS
                            ]
                        )
                        for f in range(
                            result[SCORINGS[0]].importances_mean.size
                        )
                    ]
                )
                csvfile.flush()
                del result
        finally:
            del x_train
            del x_test
            del y_train
            del y_test
    else:
        print(f"Skipping since {file} does not exist.")
        sys.stdout.flush()
    sys.stdout.flush()


if __name__ == "__main__":
    main()
