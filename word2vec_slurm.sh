# !/bin/bash
#
# word2vec_slurm.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=262144
#SBATCH --time=12:00:00
#SBATCH --gres=gpu:1
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=262144
#SBATCH --time=12:00:00
#SBATCH --gres=gpu:1
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=262144
#SBATCH --time=12:00:00
#SBATCH --gres=gpu:1
#SBATCH hetjob
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=262144
#SBATCH --time=12:00:00
#SBATCH --gres=gpu:1

module purge
module load release/24.10 GCCcore/13.3.0 CUDA/12.6.0 Python/3.12.3

# . "${PWD}"/.env/bin/activate && \
#     pip install -r "${PWD}"/requirements.txt &&
#     pip install --extra-index-url=https://pypi.nvidia.com "cuml-cu12==25.6.*"
export INPUT_PATH=/data/horse/ws/male646f-pivot-eval/
srun ./word2vec_log.sh -p coaps 	: \
     ./word2vec_log.sh -p coap https	: \
     ./word2vec_log.sh -p oscore	: \
     ./word2vec_log.sh -p oscore-base

wait
