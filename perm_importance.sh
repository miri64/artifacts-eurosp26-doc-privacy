#! /bin/bash
#
# perm_importance.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

SCRIPT_DIR=$( cd -- "$( dirname -- "$(realpath "$0")" )" &> /dev/null && pwd )
PROCS=$(grep -c '^processor' /proc/cpuinfo)
if [ $PROCS -gt 6 ]; then
    # Cap to keep in memory limits
    PROCS=6
fi
INPUT_PATH="${INPUT_PATH:-${SCRIPT_DIR}/output_dataset}"

perm_importance() {
    export POLARS_FORCE_NEW_STREAMING=1
    export INPUT_PATH
    ./perm_importance.py "$1"
}

export -f perm_importance
export INPUT_PATH
echo "Running on ${PROCS} workers"
./list_scenarios.py -r $* | parallel -j "${PROCS}" perm_importance
