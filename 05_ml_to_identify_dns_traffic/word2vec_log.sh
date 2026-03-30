# !/bin/bash
#
# word2vec_log.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

name=$(echo "$*" | cut -d' ' -f2)


"${PWD}"/.env/bin/python "${PWD}"/word2vec.sh $* &> "${INPUT_PATH}/word2vec_${name}_${SLURM_JOB_ID}.log"
