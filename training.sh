#!/bin/bash


while getopts ":p:r:v:" opt; do
    case "${opt}" in
    p)  prots="${prots}_${OPTARG}";;
    r)  run="${OPTARG}";;
    v)  vec="${OPTARG}";;
    *)  prots="${prots}_${OPTARG}";;
    esac
done

"${PWD}"/.env/bin/python "${PWD}"/training.py $* &> "${INPUT_PATH}/training${prots}_${vec}_${run}_${SLURM_JOB_ID}.log"
