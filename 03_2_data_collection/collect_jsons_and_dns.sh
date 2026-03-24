#! /bin/bash
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

SCRIPT_PATH="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
INPUT_PATH="${INPUT_PATH:-${SCRIPT_PATH}/../input_dataset}"
OUTPUT_PATH="${OUTPUT_PATH:-${SCRIPT_PATH}/../input_dataset}"
PROCS=$(grep -c '^processor' /proc/cpuinfo)
NAMESERVER="${1:-9.9.9.9}"

"${SCRIPT_PATH}"/collect_jsons_and_dns.py -0 > "${OUTPUT_PATH}/2024-09-01-sample.csv"
tar -C "${INPUT_PATH}" -xOf "${INPUT_PATH}/"bq-results.tar.xz bq-results-20241115-171644-1731691029838.csv bq-results-20241115-172202-1731691391614.csv | \
    parallel -j"${PROCS}" --line-buffer --pipe "${SCRIPT_PATH}"/collect_jsons_and_dns.py -s "${NAMESERVER}" \
    >> "${OUTPUT_PATH}/2024-09-01-sample.csv" 2> "${OUTPUT_PATH}/2024-09-01-sample.errors.log"
