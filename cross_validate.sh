#! /bin/bash
#
# training.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

while getopts ":c:p:D:d:l:n:r:v:" opt; do
    case "${opt}" in
    c)  cls="${OPTARG}";;
    p)  prots="${prots}_${OPTARG}";;
    D)  data="${data}_${OPTARG}";;
    d)  dns="${dns}_${OPTARG}";;
    l)  link_layer="${link_layer}_${OPTARG}";;
    n)  network_setups="${network_setups}_${OPTARG}";;
    v)  vec="${OPTARG}";;
    *)  prots="${prots}_${OPTARG}";;
    esac
done

VENV=${VENV:-"${PWD}"/.env}

"${VENV}"/bin/python "${PWD}"/cross_validate.py $* \
    &> "${INPUT_PATH}/cross_validation_${cls}_${step}${prots}${network_setups}${link_layer}${data}${dns}_${vec}_${SLURM_JOB_ID}.log"
