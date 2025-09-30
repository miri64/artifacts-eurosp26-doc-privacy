#! /bin/bash
#
# training.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

SCRIPT_DIR=$( cd -- "$( dirname -- "$(realpath "$0")" )" &> /dev/null && pwd )
VENV=${VENV:-"${SCRIPT_DIR}"/.env}
INPUT_PATH="${INPUT_PATH:-${SCRIPT_DIR}/output_dataset}"
CLASSIFIERS=(
    "lr"
    "knn"
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

"${VENV}"/bin/python "${SCRIPT_DIR}"/list_scenarios.py $args | while read scenario; do
    for cls in "${CLASSIFIERS[@]}"; do
        if [[ -n "${classifier}" && "$cls" != "${classifier}" ]]; then
            continue
        fi
        "${VENV}"/bin/python "${SCRIPT_DIR}"/cross_validate.py -v "${vec}" "${scenario}" "${cls}"
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
done &> "${INPUT_PATH}/cross_validation_${classifier}_${step}${prots}${network_setups}${link_layer}${data}${dns}_${vec}_${SLURM_JOB_ID}.log"
