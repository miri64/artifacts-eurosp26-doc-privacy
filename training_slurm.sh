#!/bin/bash

#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=752520
#SBATCH --gres=gpu:1
#SBATCH --time=48:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=752520
#SBATCH --gres=gpu:1
#SBATCH --time=48:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=752520
#SBATCH --gres=gpu:1
#SBATCH --time=48:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=752520
#SBATCH --gres=gpu:1
#SBATCH --time=48:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=752520
#SBATCH --gres=gpu:1
#SBATCH --time=48:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=752520
#SBATCH --gres=gpu:1
#SBATCH --time=48:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=752520
#SBATCH --gres=gpu:1
#SBATCH --time=48:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=752520
#SBATCH --gres=gpu:1
#SBATCH --time=48:00:00

module purge
module load release/24.10 GCCcore/13.3.0 CUDA/12.6.0 Python/3.12.3

# . "${PWD}"/.env/bin/activate && \
# 	pip install --upgrade -r "${PWD}"/requirements.txt &&
# 	pip install --upgrade --extra-index-url=https://pypi.nvidia.com "cuml-cu12==25.6.*"
export INPUT_PATH=/data/horse/ws/male646f-pivot-eval/

RUN="${1:-1}"

srun "${PWD}"/training.sh -p coaps          -r "${RUN}" -v word2vec : \
     "${PWD}"/training.sh -p coap -p https  -r "${RUN}" -v word2vec : \
     "${PWD}"/training.sh -p oscore         -r "${RUN}" -v word2vec : \
     "${PWD}"/training.sh -p oscore-base    -r "${RUN}" -v word2vec : \
     "${PWD}"/training.sh -p coaps          -r "${RUN}" -v binvec : \
     "${PWD}"/training.sh -p coap -p https  -r "${RUN}" -v binvec : \
     "${PWD}"/training.sh -p oscore         -r "${RUN}" -v binvec : \
     "${PWD}"/training.sh -p oscore-base    -r "${RUN}" -v binvec
wait
