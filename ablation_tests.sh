#! /bin/bash
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

while getopts ":c:s:p:D:d:l:r:v:" opt; do
    case "${opt}" in
    c)  cls="${OPTARG}";;
    s)  step="${OPTARG}";;
    p)  prots="${prots}_${OPTARG}";;
    D)  data="${data}_${OPTARG}";;
    d)  dns="${dns}_${OPTARG}";;
    l)  link_layer="${link_layer}_${OPTARG}";;
    r)  run="${OPTARG}";;
    v)  vec="${OPTARG}";;
    *)  prots="${prots}_${OPTARG}";;
    esac
done

"${PWD}"/.env/bin/python "${PWD}"/ablation_tests.py $* \
    &> "${INPUT_PATH}/ablation_${cls}_${step}${prots}${link_layer}${data}${dns}_${vec}_${run}_${SLURM_JOB_ID}.log"
