#! /bin/bash
#
# count_client_logs.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

SCRIPT_DIR=$( cd -- "$( dirname -- "$(realpath "$0")" )" &> /dev/null && pwd )
OUTPUT_DATASETS="$(readlink -f "${OUTPUT_DATASETS:-${SCRIPT_DIR}/../output_dataset}")"

awk '
    {
        timestamps[FILENAME][$1 * 10**9] += 1
    }
    END {
        for (fn in timestamps) {
            sum = 0; min=0;
            for (ts in timestamps[fn]) {
                if ((!min || min > ts) && ts != 0) { min = ts }
                sum += timestamps[fn][ts]
            }
            print min, fn, length(timestamps[fn]), sum
        }
    }' "${OUTPUT_DATASETS}"/*.client.log | \
        sort -n | awk 'BEGIN {print "Requests", "Messages", "Log"} {print $3, $4, $2}'
