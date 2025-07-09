#! /bin/bash
#
# binvec.sh
# Copyright (C) 2025 Martine S. Lenders <martine.lenders@tu-dresden.de>
#
# Distributed under terms of the MIT license.
#

SCRIPT_DIR=$( cd -- "$( dirname -- "$(realpath "$0")" )" &> /dev/null && pwd )
PROCS=$(grep -c '^processor' /proc/cpuinfo)
if [ $PROCS -gt 16 ]; then
    # Every process needs a lot of memory
    PROCS=16
fi
INPUT_PATH="${INPUT_PATH:-${SCRIPT_DIR}/output_dataset}"

binvec() {
    export POLARS_FORCE_NEW_STREAMING=1
    export INPUT_PATH
    ./binvec.py "$1"
}

export -f binvec
export INPUT_PATH
./list_scenarios.py $* | parallel -j "${PROCS}" binvec
