#! /usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

import argparse
import concurrent.futures
import multiprocessing
import os
import pathlib
import sys
import traceback
import warnings

import polars
import numpy


EVALUATION_DIR = pathlib.Path.cwd()
INPUT_PATH = pathlib.Path(
    os.environ.get("INPUT_PATH", EVALUATION_DIR / "output_dataset")
)
WORKERS = multiprocessing.cpu_count()

if WORKERS > 8:
    WORKERS = 8


def scenario2vec(scenario):
    file = INPUT_PATH / f"{scenario}.training.csv.gz" 
    vector_file = INPUT_PATH / f"{scenario}.binvec.parquet"

    if not file.exists():
        print(f"Skipping {file} since it does not exist")
        return
    elif vector_file.exists():
        print(f"Skipping {file} since {vector_file} exists")
        return
    print("Processing", str(file))

    df = polars.scan_csv(file, separator=";").with_columns(
        polars.col("eth.payload").map_elements(
            lambda hex_msg: numpy.concatenate(
                [
                    # convert hex nibbles to bits
                    [int(b) for b in bin(int(x, base=16))[2:].zfill(4)]
                    # Padding is marked with "x", use 2 for padding in binary space
                    if x != "x" else ([2] * 4)
                    for x in hex_msg
                ]
            ).tolist(),
            return_dtype=polars.List(polars.Int8),
        ),
        (polars.col("client.type") == "dns").cast(
            polars.Int8
        )
    ).select(
        polars.col("eth.payload"),
        polars.col("client.type"),
    ).rename(
        {"eth.payload": "vector", "client.type": "label"}
    ).sink_parquet(vector_file, compression="lz4")
    del df
    print("Created", str(vector_file))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "scenario",
        help="Name of the scenario to train for",
    )
    args = parser.parse_args()

    scenario2vec(args.scenario)


if __name__ == "__main__":
    main()
