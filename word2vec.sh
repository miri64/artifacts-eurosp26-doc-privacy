#! /bin/bash
#
# word2vec.sh
# Copyright (C) 2025 Martine S. Lenders <martine.lenders@tu-dresden.de>
#
# Distributed under terms of the MIT license.
#

SCRIPT_DIR=$( cd -- "$( dirname -- "$(realpath "$0")" )" &> /dev/null && pwd )
PROCS=$(grep -c '^processor' /proc/cpuinfo)
if [ $PROCS -gt 8 ]; then
    # Every process needs a lot of memory
    PROCS=8  # $(( (PROCS * 3) / 4))
fi
INPUT_PATH="${INPUT_PATH:-${SCRIPT_DIR}/output_dataset}"

word2vec() {
    export INPUT_PATH
    ./word2vec.py "$1"
}

export -f word2vec
export INPUT_PATH
./list_scenarios.py $* | parallel -j "${PROCS}" word2vec
