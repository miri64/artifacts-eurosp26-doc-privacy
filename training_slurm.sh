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

module purge
module load release/24.10 GCCcore/13.3.0 CUDA/12.6.0 Python/3.12.3

# . "${PWD}"/.env/bin/activate && \
# 	pip install --upgrade -r "${PWD}"/requirements.txt &&
# 	pip install --upgrade --extra-index-url=https://pypi.nvidia.com "cuml-cu12==25.6.*"
export INPUT_PATH=/data/horse/ws/male646f-pivot-eval/

srun "'${PWD}'/.env/bin/python '${PWD}'/training.py -p coaps          &> ${INPUT_PATH}/training_coaps.log" : \
     "'${PWD}'/.env/bin/python '${PWD}'/training.py -p coap https     &> ${INPUT_PATH}/training_coap.log" : \
     "'${PWD}'/.env/bin/python '${PWD}'/training.py -p oscore         &> ${INPUT_PATH}/training_oscore.log" : \
     "'${PWD}'/.env/bin/python '${PWD}'/training.py -p oscore-base    &> ${INPUT_PATH}/training_oscore-base.log"
wait
