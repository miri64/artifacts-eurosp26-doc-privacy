#! /bin/bash
#
# training.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

SCRIPT_DIR=$( cd -- "$( dirname -- "$(realpath "$0")" )" &> /dev/null && pwd )
INPUT_PATH="${INPUT_PATH:-${SCRIPT_DIR}/../output_dataset}"
CLASSIFIERS=(
    "lr"
    "knn"
    # Our datasets have >4.7 billion (> 2 * 120699 * 1219 * 16) samples for which SVM
    # does not scale (not recommended for >1 million, 10-100k samples are best, see
    # https://github.com/scikit-learn/scikit-learn/issues/18027#issuecomment-800873636
    # ). For our particular datasets it crashes due to Int32 overflow error.
    # We keep the code for smaller samples and CUDA though.
    "svm"
    "dt"
    "rf"
    "ab"
)

vec="binvec"
args=""

while getopts ":c:D:d:l:n:p:r:v:" opt; do
    case "${opt}" in
    c)  classifier="${OPTARG}";;
    p)  prots="${prots}_${OPTARG}"; args="${args} -p ${OPTARG}";;
    D)  data="${data}_${OPTARG}"; args="${args} -D ${OPTARG}";;
    d)  dns="${dns}_${OPTARG}"; args="${args} -d ${OPTARG}";;
    l)  link_layer="${link_layer}_${OPTARG}"; args="${args} -l ${OPTARG}";;
    n)  network_setups="${network_setups}_${OPTARG}"; args="${args} -n ${OPTARG}";;
    v)  vec="${OPTARG}";;
    *)  prots="${prots}_${OPTARG}"; args="${args} -p ${OPTARG}";;
    esac
done

export POLARS_FORCE_NEW_STREAMING=1

# due to the massive memory usage we can not parallelize this approach on one machine
for scenario in $("${SCRIPT_DIR}"/../list_scenarios.py $args); do
    for cls in "${CLASSIFIERS[@]}"; do
        if [[ -n "${classifier}" && "$cls" != "${classifier}" ]]; then
            continue
        fi
        "${SCRIPT_DIR}"/cross_validate.py -v "${vec}" "${scenario}" "${cls}"
        RESULT="$?"
        if [[ "${RESULT}" -eq 128 || "${RESULT}" -eq 2 ]]; then
            # error code indicates that all classifiers where already evaluated or arguments were
            # wrong, take next scenario
            break
        fi
    done
    if [[ "${RESULT}" -eq 2 ]]; then
        break
    fi
done
