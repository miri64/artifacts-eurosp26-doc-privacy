#!/bin/bash

#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem-per-cpu=65536
#SBATCH --gres=gpu:1
#SBATCH --time=08:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem-per-cpu=65536
#SBATCH --gres=gpu:1
#SBATCH --time=08:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem-per-cpu=65536
#SBATCH --gres=gpu:1
#SBATCH --time=08:00:00
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem-per-cpu=65536
#SBATCH --gres=gpu:1
#SBATCH --time=08:00:00

module purge
module load release/24.10 GCCcore/13.3.0 CUDA/12.6.0 Python/3.12.3

# . "${PWD}"/.env/bin/activate && \
# 	pip install --upgrade -r "${PWD}"/requirements.txt &&
# 	pip install --upgrade --extra-index-url=https://pypi.nvidia.com "cuml-cu12==25.6.*"
export INPUT_PATH=/data/horse/ws/male646f-pivot-eval/
srun "${PWD}"/.env/bin/python "${PWD}"/word2vec.py -p coaps       : \
     "${PWD}"/.env/bin/python "${PWD}"/word2vec.py -p coap        : \
     "${PWD}"/.env/bin/python "${PWD}"/word2vec.py -p oscore      : \
     "${PWD}"/.env/bin/python "${PWD}"/word2vec.py -p oscore-base 

wait

srun "${PWD}"/.env/bin/python "${PWD}"/training.py -p coaps      : \
     "${PWD}"/.env/bin/python "${PWD}"/training.py -p coap       : \
     "${PWD}"/.env/bin/python "${PWD}"/training.py -p oscore     : \
     "${PWD}"/.env/bin/python "${PWD}"/training.py -p oscore-base
wait
