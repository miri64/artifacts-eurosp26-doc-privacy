#!/bin/bash
#
# ablation_tests_slurm.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=193250
#SBATCH --gres=gpu:1
#SBATCH --time=48:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=193250
#SBATCH --gres=gpu:1
#SBATCH --time=48:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=193250
#SBATCH --gres=gpu:1
#SBATCH --time=48:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=193250
#SBATCH --gres=gpu:1
#SBATCH --time=48:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=193250
#SBATCH --gres=gpu:1
#SBATCH --time=48:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=193250
#SBATCH --gres=gpu:1
#SBATCH --time=48:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=193250
#SBATCH --gres=gpu:1
#SBATCH --time=48:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=193250
#SBATCH --gres=gpu:1
#SBATCH --time=48:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=193250
#SBATCH --gres=gpu:1
#SBATCH --time=48:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=193250
#SBATCH --gres=gpu:1
#SBATCH --time=48:00:00

module purge
module load release/24.10 GCCcore/13.3.0 CUDA/12.6.0 Python/3.12.3

# . "${PWD}"/.env/bin/activate && \
# 	pip install --upgrade -r "${PWD}"/requirements.txt &&
# 	pip install --upgrade --extra-index-url=https://pypi.nvidia.com "cuml-cu12==25.6.*"
export INPUT_PATH=/data/horse/ws/male646f-pivot-eval/

RUN="${1:-1}"
srun "${PWD}"/ablation_tests.sh -c dt -s 8 -p coaps         -D json -d dns_message -d dns_cbor  -r "${RUN}" -v binvec : \
     "${PWD}"/ablation_tests.sh -c dt -s 8 -p coap          -D json -d dns_message -d dns_cbor  -r "${RUN}" -v binvec : \
     "${PWD}"/ablation_tests.sh -c dt -s 8 -p https         -D json -d dns_message -d dns_cbor  -r "${RUN}" -v binvec : \
     "${PWD}"/ablation_tests.sh -c dt -s 8 -p oscore        -D json -d dns_message -d dns_cbor  -r "${RUN}" -v binvec : \
     "${PWD}"/ablation_tests.sh -c dt -s 8 -p oscore-base   -D json -d dns_message -d dns_cbor  -r "${RUN}" -v binvec : \
     "${PWD}"/ablation_tests.sh -c dt -s 8 -p coaps         -D cbor -d dns_message -d dns_cbor  -r "${RUN}" -v binvec : \
     "${PWD}"/ablation_tests.sh -c dt -s 8 -p coap          -D cbor -d dns_message -d dns_cbor  -r "${RUN}" -v binvec : \
     "${PWD}"/ablation_tests.sh -c dt -s 8 -p https         -D cbor -d dns_message -d dns_cbor  -r "${RUN}" -v binvec : \
     "${PWD}"/ablation_tests.sh -c dt -s 8 -p oscore        -D cbor -d dns_message -d dns_cbor  -r "${RUN}" -v binvec : \
     "${PWD}"/ablation_tests.sh -c dt -s 8 -p oscore-base   -D cbor -d dns_message -d dns_cbor  -r "${RUN}" -v binvec

wait
