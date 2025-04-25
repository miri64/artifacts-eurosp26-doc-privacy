#! /usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license

import multiprocessing
import os
import pathlib

from gensim.models import word2vec
import numpy
import polars

EVALUATION_DIR = pathlib.Path.cwd()
INPUT_PATH = pathlib.Path(
    os.environ.get("INPUT_PATH", EVALUATION_DIR / "output_dataset")
)
VECTOR_SIZE = 16
WORKERS = multiprocessing.cpu_count()

if WORKERS > 96:
    WORKERS //= 2

PROTOCOLS = ["coap", "coaps", "oscore"]
LINK_LAYERS = [""]
BLOCKWISE = [""]
NETWORK_SETUPS = ["d1", "d2", "p1", "p2"]
DATA_FORMATS = ["json", "cbor"]
DNS_FORMATS = ["dns_message", "dns_cbor"]


def scenario2vec(scenario):
    file = INPUT_PATH / f"{scenario}.training.csv.gz" 
    print("Processing", str(file))
    df = polars.read_csv(file, separator=";")
    nibbles, byte_size = df["eth.payload"].str.len_chars().max(), 2

    df = df.with_columns(
        polars.col("eth.payload").map_elements(
            lambda msg: [
                msg[i : i + byte_size]
                for i in range(0, nibbles, byte_size)
            ],
            return_dtype=list[str],
        )
    )

    model = word2vec.Word2Vec(
        df["eth.payload"].to_list(),
        workers=WORKERS,
        vector_size=VECTOR_SIZE,
        min_count=1,
        window=3,
        sg=0,
    )

    df_vec = df.with_columns(
        vector=polars.col("eth.payload").map_elements(
            lambda words: numpy.concatenate(
                [model.wv[word] for word in words]
            ),
            return_dtype=polars.datatypes.List(
                polars.datatypes.Array(polars.Float32, VECTOR_SIZE)
            ),
        ),
        label=(polars.col("client.type") != "dns").cast(
            polars.Int8
        ),
    )[["vector", "label"]]
    df_vec.write_parquet(
        INPUT_PATH / f"{scenario}.vector.parquet",
        compression="zstd",
        compression_level=10,
    )
    print("Created", str(INPUT_PATH / f"{scenario}.vector.parquet"))
    del df
    del df_vec


scenarios = []
for data in DATA_FORMATS:
    for dns in DNS_FORMATS:
        for l2 in LINK_LAYERS:
            for prot in PROTOCOLS:
                for blk in BLOCKWISE:
                    for stp in NETWORK_SETUPS:
                        scenario = f"{prot}{l2}-{stp}_{data}_{dns}{blk}"
                        file = INPUT_PATH / f"{scenario}.training.csv.gz" 
                        if file.exists():
                            scenarios.append(scenario)


with multiprocessing.Pool(5 if WORKERS > 5 else WORKERS) as pool:
    pool.map(scenario2vec, scenarios)
