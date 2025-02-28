#! /bin/bash
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

SCRIPT_PATH="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
INPUT_PATH="${INPUT_PATH:-${SCRIPT_PATH}}"
OUTPUT_PATH="${OUTPUT_PATH:-${SCRIPT_PATH}}"

. ${SCRIPT_PATH}/../.env/bin/activate

"${SCRIPT_PATH}"/collect_jsons_and_dns.py -0 > "${OUTPUT_PATH}/2024-09-01-sample.csv"
cat "${INPUT_PATH}"/bq-results-20241115-171644-1731691029838.csv "${INPUT_PATH}"/bq-results-20241115-172202-1731691391614.csv | \
    parallel -j64 --line-buffer --pipe "${SCRIPT_PATH}"/collect_jsons_and_dns.py \
    >> "${OUTPUT_PATH}/2024-09-01-sample.csv" 2> "${OUTPUT_PATH}/2024-09-01-sample.errors.txt"
