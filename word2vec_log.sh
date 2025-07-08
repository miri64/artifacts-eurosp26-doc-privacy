#!/bin/bash

name=$(echo "$*" | cut -d' ' -f2)


"${PWD}"/.env/bin/python "${PWD}"/word2vec.sh $* &> "${INPUT_PATH}/word2vec_${name}_${SLURM_JOB_ID}.log"
