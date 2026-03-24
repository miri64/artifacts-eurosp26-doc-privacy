#! /bin/bash
#
# perm_importance.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

SCRIPT_DIR=$( cd -- "$( dirname -- "$(realpath "$0")" )" &> /dev/null && pwd )
VENV=${VENV:-"${SCRIPT_DIR}"/.venv}
INPUT_PATH="${INPUT_PATH:-${SCRIPT_DIR}/output_dataset}"
vec="binvec"
cls="rf"
args=""


while getopts ":c:D:d:l:n:p:rR:v:" opt; do
    case "${opt}" in
    c)  cls="${OPTARG}";;
    p)  prots="${prots}_${OPTARG}"; args="${args} -p ${OPTARG}";;
    D)  data="${data}_${OPTARG}"; args="${args} -D ${OPTARG}";;
    d)  dns="${dns}_${OPTARG}"; args="${args} -d ${OPTARG}";;
    l)  link_layer="${link_layer}_${OPTARG}"; args="${args} -l ${OPTARG}";;
    n)  network_setups="${network_setups}_${OPTARG}"; args="${args} -n ${OPTARG}";;
    r)  args="${args} -r";;
    R)  args="${args} -R ${OPTARG}";;
    v)  vec="${OPTARG}";;
    *)  prots="${prots}_${OPTARG}"; args="${args} -p ${OPTARG}";;
    esac
done

export POLARS_FORCE_NEW_STREAMING=1

# "${VENV}"/bin/python "${SCRIPT_DIR}"/list_scenarios.py $args | while read scenario; do
cat "${SCRIPT_DIR}"/missing-perm-imp.txt | parallel -j2 "${VENV}"/bin/python "${SCRIPT_DIR}"/perm_importance.py -c "${cls}" -v "${vec}" \
    &> "${INPUT_PATH}/perm_importance_${cls}_${step}${prots}${network_setups}${link_layer}${data}${dns}_${vec}_${SLURM_JOB_ID}.log"
