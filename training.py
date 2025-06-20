#! /usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

import contextlib
import csv
import os
import pathlib
import multiprocessing
import warnings

import numpy
import polars
import polars.exceptions

try:
    from cuml import ensemble as sk_ensemble
    # from cuml.exceptions import ConvergenceWarning
    from cuml import model_selection as sk_model_selection
    from cuml import linear_model as sk_linear_model
    from cuml import neighbors as sk_neighbors
    from cuml import preprocessing as sk_pp
    from cuml import svm as sk_svm
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
    from sklearn import model_selection as sk_model_selection
    from sklearn import linear_model as sk_linear_model
    from sklearn import naive_bayes as sk_nb
    from sklearn import neighbors as sk_neighbors
    from sklearn import preprocessing as sk_pp
    from sklearn import svm as sk_svm
    using_cuml = False


from sklearn.metrics import (
    confusion_matrix,
    ConfusionMatrixDisplay,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
)
from sklearn import naive_bayes as sk_nb  # cuML version of naive bayes crashed in our setup
from sklearn import tree as sk_tree


EVALUATION_DIR = pathlib.Path.cwd()
INPUT_PATH = pathlib.Path(
    os.environ.get("INPUT_PATH", EVALUATION_DIR / "output_dataset")
)

PROTOCOLS = ["coap", "coaps", "oscore", "oscore-base"]
LINK_LAYERS = [""]
BLOCKWISE = [""]
NETWORK_SETUPS = ["d1", "d2", "p1", "p2"]
DATA_FORMATS = ["json", "cbor"]
DNS_FORMATS = ["dns_message", "dns_cbor"]
TEST_SIZE = 0.2

CLASSIFIERS = [
    "nb",
    "lr",
    "knn",
    # # Our datasets have >4.7 billion (> 2 * 120699 * 1219 * 16) samples for which SVM
    # # does not scale (not recommended for >1 million, 10-100k samples are best, see
    # # https://github.com/scikit-learn/scikit-learn/issues/18027#issuecomment-800873636
    # # ).For our particular datasets it crashes due to Int32 overflow error.
    # # We keep the code for smaller samples though.
    # "svm",
    "dt",
    "rf"
]
FIELD_NAMES = [
    "protocol",
    "link_layer",
    "blocksize",
    "network_setup",
    "data_format",
    "dns_format",
    "test_size",
    "classifier",
    "classifier_args",
    "true_dns",
    "false_dns",
    "false_data",
    "true_data",
    "accuracy",
    "precision",
    "recall",
    "f1_score",
]

LINK_LAYER_READABLE = {
    "": "eth",
    "-schc": "schc",
}
BLOCKWISE_READABLE = {
    "": "1024",
    "_b16": "16",
}

CLASSIFIER_READABLE = {
    "nb": "Naïve Bayes",
    "lr": "Logistic Regression",
    "knn": "K-Nearest Neighbors",
    "svm": "Support Vector Machine",
    "dt": "Decision Tree",
    "rf": "Random Forest (Ensemble Learning III)",
}
CLASSIFIER_ARGS = {
    "nb": {},
    "lr": {"max_iter": 2800},
    "knn": {
        "algorithm": "brute",
        "n_jobs": -1,
    },
    "svm": {"C": 0.01},
    "dt": {},
    "rf": {"n_estimators": 250, "max_depth": 9},
}


@contextlib.contextmanager
def train_nb(x_train, y_train):
    nb = sk_nb.MultinomialNB().fit(x_train, y_train)
    try:
        yield nb
    finally:
        del nb


@contextlib.contextmanager
def train_lr(x_train, y_train):
    while True:
        warnings.filterwarnings("error")
        try:
            lr = sk_linear_model.LogisticRegression(**CLASSIFIER_ARGS["lr"])
            lr.fit(x_train, numpy.ravel(y_train))
            print("- Converged at", CLASSIFIER_ARGS["lr"])
            break
        except sk_exceptions.ConvergenceWarning:
            CLASSIFIER_ARGS["lr"]["max_iter"] += 200
            print("- Updated args to", CLASSIFIER_ARGS["lr"])
        finally:
            warnings.resetwarnings()
    try:
        yield lr
    finally:
        del lr


@contextlib.contextmanager
def train_knn(x_train, y_train):
    knn = sk_neighbors.KNeighborsClassifier(**CLASSIFIER_ARGS["knn"])
    knn.fit(x_train, numpy.ravel(y_train))
    try:
        yield knn
    finally:
        del knn


@contextlib.contextmanager
def train_svm(x_train, y_train):
    svm = sk_svm.LinearSVC(**CLASSIFIER_ARGS["svm"])
    svm.fit(x_train, numpy.ravel(y_train))
    try:
        yield svm
    finally:
        del svm


@contextlib.contextmanager
def train_dt(x_train, y_train):
    dt = sk_tree.DecisionTreeClassifier(**CLASSIFIER_ARGS["dt"])
    dt.fit(x_train, y_train)
    try:
        yield dt
    finally:
        del dt


@contextlib.contextmanager
def train_rf(x_train, y_train):
    # n_estimators = number of decision trees
    rf = sk_ensemble.RandomForestClassifier(**CLASSIFIER_ARGS["rf"])
    rf.fit(x_train, numpy.ravel(y_train))
    try:
        yield rf
    finally:
        del rf


def test(classifier, x_test, y_test):
    y_test_predictions = classifier.predict(x_test)
    conf_matrix = confusion_matrix(y_test, y_test_predictions)
    accuracy = accuracy_score(y_test, y_test_predictions)
    precision = precision_score(y_test, y_test_predictions)
    recall = recall_score(y_test, y_test_predictions)
    f1score = f1_score(y_test, y_test_predictions)
    del y_test_predictions
    return conf_matrix, accuracy, precision, recall, f1score


TRAIN = {
    "nb": train_nb,
    "lr": train_lr,
    "knn": train_knn,
    "svm": train_svm,
    "dt": train_dt,
    "rf": train_rf,
}


def str_classifier_args(classifier):
    args = ",".join(f"{k}={v}" for k, v in CLASSIFIER_ARGS[classifier].items())
    if args:
        return args
    return None


def main():
    if using_cuml:
        CLASSIFIERS.insert(3, "svm")
        CLASSIFIER_ARGS["lr"]["max_iter"] = 5000
        del CLASSIFIER_ARGS["knn"]["n_jobs"]
        print("Using cuML")
    for data in DATA_FORMATS:
        for dns in DNS_FORMATS:
            for l2 in LINK_LAYERS:
                for prot in PROTOCOLS:
                    for blk in BLOCKWISE:
                        for stp in NETWORK_SETUPS:
                            scenario = f"{prot}{l2}-{stp}_{data}_{dns}{blk}"
                            print(f"# {scenario}")
                            file = INPUT_PATH / f"{scenario}.vector.parquet"
                            results_file = INPUT_PATH / f"{scenario}.results.csv"
                            if results_file.exists():
                                try:
                                    df = polars.read_csv(results_file)
                                    if set(
                                        tuple(d.values())
                                        for d in df.filter(
                                            (df["protocol"] == prot)
                                            & (df["link_layer"] == LINK_LAYER_READABLE[l2])
                                            & (df["blocksize"] == BLOCKWISE_READABLE[blk])
                                            & (df["network_setup"] == stp)
                                            & (df["data_format"] == data)
                                            & (df["dns_format"] == dns)
                                            & (df["test_size"] == TEST_SIZE)
                                        )[["classifier", "classifier_args"]].to_dicts()
                                    ) == set(
                                        (c, str_classifier_args(c)) for c in CLASSIFIERS
                                    ):
                                        print(
                                            " - Skipping since results for all classifiers "
                                            f"are in {results_file.relative_to(INPUT_PATH)}"
                                        )
                                        continue
                                except polars.exceptions.NoDataError:
                                    df = None
                            else:
                                df = None

                            if file.exists():
                                df_vec = polars.read_parquet(file)
                                df_vec = df_vec.cast(
                                    {
                                        "vector": polars.Array(
                                            polars.Float32,
                                            df_vec["vector"].list.len().max(),
                                        )
                                    }
                                )
                                x = df_vec["vector"].to_numpy()
                                y = df_vec["label"].to_numpy()
                                del df_vec
                                x_train, x_test, y_train, y_test = (
                                    sk_model_selection.train_test_split(
                                        x, y, test_size=TEST_SIZE
                                    )
                                )
                                del x
                                del y
                                scaler = sk_pp.MinMaxScaler()
                                x_train_minmax = scaler.fit_transform(x_train)
                                x_test_minmax = scaler.transform(x_test)
                                del x_train
                                del x_test
                                with open(
                                    results_file, "w" if df is None else "a"
                                ) as csvfile:
                                    writer = csv.DictWriter(
                                        csvfile, fieldnames=FIELD_NAMES
                                    )
                                    if df is None:
                                        writer.writeheader()
                                    for cls in CLASSIFIERS:
                                        print(f"## {CLASSIFIER_READABLE[cls]}")
                                        if (
                                            df is not None
                                            and not df.filter(
                                                (df["protocol"] == prot)
                                                & (
                                                    df["link_layer"]
                                                    == LINK_LAYER_READABLE[l2]
                                                )
                                                & (
                                                    df["blocksize"]
                                                    == BLOCKWISE_READABLE[blk]
                                                )
                                                & (df["network_setup"] == stp)
                                                & (df["data_format"] == data)
                                                & (df["dns_format"] == dns)
                                                & (df["test_size"] == TEST_SIZE)
                                                & (df["classifier"] == cls)
                                                & (
                                                    (
                                                        df["classifier_args"]
                                                        == str_classifier_args(cls)
                                                    )
                                                    if str_classifier_args(cls)
                                                    else df["classifier_args"].is_null()
                                                )
                                            ).is_empty()
                                        ):
                                            print(
                                                " - Skipping since it is already in",
                                                results_file.relative_to(INPUT_PATH),
                                            )
                                            continue
                                        with TRAIN[cls](
                                            x_train_minmax, y_train
                                        ) as classifier:
                                            (
                                                conf_matrix,
                                                accuracy,
                                                precision,
                                                recall,
                                                f1score,
                                            ) = test(classifier, x_test_minmax, y_test)
                                        writer.writerow(
                                            {
                                                "protocol": prot,
                                                "link_layer": LINK_LAYER_READABLE[l2],
                                                "blocksize": BLOCKWISE_READABLE[blk],
                                                "network_setup": stp,
                                                "data_format": data,
                                                "dns_format": dns,
                                                "test_size": TEST_SIZE,
                                                "classifier": cls,
                                                "classifier_args": str_classifier_args(
                                                    cls
                                                ),
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


if __name__ == "__main__":
    main()
