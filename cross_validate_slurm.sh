#!/bin/bash
#
# training_slurm.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=386500
#SBATCH --gres=gpu:2
#SBATCH --time=24:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=386500
#SBATCH --gres=gpu:2
#SBATCH --time=24:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=386500
#SBATCH --gres=gpu:2
#SBATCH --time=24:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=386500
#SBATCH --gres=gpu:2
#SBATCH --time=24:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=386500
#SBATCH --gres=gpu:2
#SBATCH --time=24:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=386500
#SBATCH --gres=gpu:2
#SBATCH --time=24:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=386500
#SBATCH --gres=gpu:2
#SBATCH --time=24:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=386500
#SBATCH --gres=gpu:2
#SBATCH --time=24:00:00

module purge
module load release/24.10 GCCcore/13.3.0 CUDA/12.6.0 Python/3.12.3

. "${PWD}"/.env/bin/activate && \
 	pip install --upgrade uv &&
 	uv pip install --upgrade -r "${PWD}"/requirements.txt &&
 	uv pip install --upgrade --extra-index-url=https://pypi.nvidia.com "cuml-cu12==25.6.*"
export INPUT_PATH=/data/horse/ws/male646f-pivot-eval/

srun "${PWD}"/cross_validate.sh -p coaps          -D "json" -v binvec : \
     "${PWD}"/cross_validate.sh -p coap -p https  -D "json" -v binvec : \
     "${PWD}"/cross_validate.sh -p oscore         -D "json" -v binvec : \
     "${PWD}"/cross_validate.sh -p oscore-base    -D "json" -v binvec : \
     "${PWD}"/cross_validate.sh -p coaps          -D "cbor" -v binvec : \
     "${PWD}"/cross_validate.sh -p coap -p https  -D "cbor" -v binvec : \
     "${PWD}"/cross_validate.sh -p oscore         -D "cbor" -v binvec : \
     "${PWD}"/cross_validate.sh -p oscore-base    -D "cbor" -v binvec
wait
