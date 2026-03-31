#!/bin/bash
#
# training_slurm.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=376260
#SBATCH --gres=gpu:2
#SBATCH --time=144:00:00
#SBATCH hetjob
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=376260
#SBATCH --gres=gpu:2
#SBATCH --time=144:00:00
#SBATCH hetjob
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=376260
#SBATCH --gres=gpu:2
#SBATCH --time=144:00:00
#SBATCH hetjob
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=376260
#SBATCH --gres=gpu:2
#SBATCH --time=144:00:00
#SBATCH hetjob
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=376260
#SBATCH --gres=gpu:2
#SBATCH --time=144:00:00
#SBATCH hetjob
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=376260
#SBATCH --gres=gpu:2
#SBATCH --time=144:00:00
#SBATCH hetjob
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=376260
#SBATCH --gres=gpu:2
#SBATCH --time=144:00:00
#SBATCH hetjob
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=376260
#SBATCH --gres=gpu:2
#SBATCH --time=144:00:00
#SBATCH hetjob
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=376260
#SBATCH --gres=gpu:2
#SBATCH --time=144:00:00
#SBATCH hetjob
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=376260
#SBATCH --gres=gpu:2
#SBATCH --time=144:00:00
#SBATCH hetjob
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=376260
#SBATCH --gres=gpu:2
#SBATCH --time=144:00:00
#SBATCH hetjob
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=376260
#SBATCH --gres=gpu:2
#SBATCH --time=144:00:00
#SBATCH hetjob
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=376260
#SBATCH --gres=gpu:2
#SBATCH --time=144:00:00
#SBATCH hetjob
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=376260
#SBATCH --gres=gpu:2
#SBATCH --time=144:00:00
#SBATCH hetjob
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=376260
#SBATCH --gres=gpu:2
#SBATCH --time=144:00:00
#SBATCH hetjob
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=376260
#SBATCH --gres=gpu:2
#SBATCH --time=144:00:00

module purge
module load release/24.10 GCCcore/13.3.0 CUDA/12.6.0 Python/3.12.3

SCRIPT_PATH="${PWD}"
export INPUT_PATH="${INPUT_PATH:-${SCRIPT_PATH}/../output_dataset}"
export VENV="${VENV:-${INPUT_PATH}/.env-cuml}"
export PYTHON_EXEC="${PYTHON_EXEC:-${VENV}/bin/python}"

if ! [ -f "${VENV}"/bin/activate ]; then
    python -m venv "${VENV}"
fi	

# You can comment this out if you already installed the requirements 
. "${VENV}"/bin/activate && \
  	pip install --upgrade uv &&
  	uv pip install --upgrade -r "${PWD}"/requirements.txt &&
  	pip install --upgrade --extra-index-url=https://pypi.nvidia.com "cuml-cu12==25.6.*"
# installing from pypi.nvidia.com does not work with uv...

srun "${PYTHON_EXEC}" "${SCRIPT_PATH}"/perm_importance.sh -r -c rf -p coaps          -D "json" -d "dns_message" -v binvec : \
     "${PYTHON_EXEC}" "${SCRIPT_PATH}"/perm_importance.sh -r -c rf -p coap -p https  -D "json" -d "dns_message" -v binvec : \
     "${PYTHON_EXEC}" "${SCRIPT_PATH}"/perm_importance.sh -r -c rf -p oscore         -D "json" -d "dns_message" -v binvec : \
     "${PYTHON_EXEC}" "${SCRIPT_PATH}"/perm_importance.sh -r -c rf -p oscore-base    -D "json" -d "dns_message" -v binvec : \
     "${PYTHON_EXEC}" "${SCRIPT_PATH}"/perm_importance.sh -r -c rf -p coaps          -D "cbor" -d "dns_message" -v binvec : \
     "${PYTHON_EXEC}" "${SCRIPT_PATH}"/perm_importance.sh -r -c rf -p coap -p https  -D "cbor" -d "dns_message" -v binvec : \
     "${PYTHON_EXEC}" "${SCRIPT_PATH}"/perm_importance.sh -r -c rf -p oscore         -D "cbor" -d "dns_message" -v binvec : \
     "${PYTHON_EXEC}" "${SCRIPT_PATH}"/perm_importance.sh -r -c rf -p oscore-base    -D "cbor" -d "dns_message" -v binvec : \
     "${PYTHON_EXEC}" "${SCRIPT_PATH}"/perm_importance.sh -r -c rf -p coaps          -D "json" -d "dns_cbor"    -v binvec : \
     "${PYTHON_EXEC}" "${SCRIPT_PATH}"/perm_importance.sh -r -c rf -p coap -p https  -D "json" -d "dns_cbor"    -v binvec : \
     "${PYTHON_EXEC}" "${SCRIPT_PATH}"/perm_importance.sh -r -c rf -p oscore         -D "json" -d "dns_cbor"    -v binvec : \
     "${PYTHON_EXEC}" "${SCRIPT_PATH}"/perm_importance.sh -r -c rf -p oscore-base    -D "json" -d "dns_cbor"    -v binvec : \
     "${PYTHON_EXEC}" "${SCRIPT_PATH}"/perm_importance.sh -r -c rf -p coaps          -D "cbor" -d "dns_cbor"    -v binvec : \
     "${PYTHON_EXEC}" "${SCRIPT_PATH}"/perm_importance.sh -r -c rf -p coap -p https  -D "cbor" -d "dns_cbor"    -v binvec : \
     "${PYTHON_EXEC}" "${SCRIPT_PATH}"/perm_importance.sh -r -c rf -p oscore         -D "cbor" -d "dns_cbor"    -v binvec : \
     "${PYTHON_EXEC}" "${SCRIPT_PATH}"/perm_importance.sh -r -c rf -p oscore-base    -D "cbor" -d "dns_cbor"    -v binvec
wait
