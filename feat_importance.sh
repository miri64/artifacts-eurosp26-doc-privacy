#! /bin/bash
#
# feat_importance.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

SCRIPT_DIR=$( cd -- "$( dirname -- "$(realpath "$0")" )" &> /dev/null && pwd )
PROCS=$(grep -c '^processor' /proc/cpuinfo)
if [ $PROCS -gt 4 ]; then
    # Cap to keep in memory limits
    PROCS=4
fi
INPUT_PATH="${INPUT_PATH:-${SCRIPT_DIR}/output_dataset}"

feat_importance() {
    export POLARS_FORCE_NEW_STREAMING=1
    export INPUT_PATH
    ./feat_importance.py "$1"
}

export -f feat_importance
export INPUT_PATH
echo "Running on ${PROCS} workers"
./list_scenarios.py $* | parallel -j "${PROCS}" feat_importance
