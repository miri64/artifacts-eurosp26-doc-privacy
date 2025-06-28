#!/bin/bash

#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=262144
#SBATCH --time=06:00:00
#SBATCH --gres=gpu:1
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=262144
#SBATCH --time=06:00:00
#SBATCH --gres=gpu:1
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=262144
#SBATCH --time=06:00:00
#SBATCH --gres=gpu:1
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=262144
#SBATCH --time=06:00:00
#SBATCH --gres=gpu:1

module purge
module load release/24.10 GCCcore/13.3.0 CUDA/12.6.0 Python/3.12.3

# . "${PWD}"/.env/bin/activate && \
#     pip install -r "${PWD}"/requirements.txt &&
#     pip install --extra-index-url=https://pypi.nvidia.com "cuml-cu12==25.6.*"
export INPUT_PATH=/data/horse/ws/male646f-pivot-eval/
srun "'${PWD}'/.env/bin/python '${PWD}'/word2vec.py -p coaps          &> ${INPUT_PATH}/word2vec_coaps.log" : \
     "'${PWD}'/.env/bin/python '${PWD}'/word2vec.py -p coap https     &> ${INPUT_PATH}/word2vec_coap.log" : \
     "'${PWD}'/.env/bin/python '${PWD}'/word2vec.py -p oscore         &> ${INPUT_PATH}/word2vec_oscore.log" : \
     "'${PWD}'/.env/bin/python '${PWD}'/word2vec.py -p oscore-base    &> ${INPUT_PATH}/word2vec_oscore-base.log"

wait
