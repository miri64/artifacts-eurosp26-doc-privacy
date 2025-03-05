#! /bin/sh
#
# coap_server.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

SCRIPT_DIR=$( cd -- "$( dirname -- "$(realpath "$0")" )" &> /dev/null && pwd )

if [ -n "${SERVER_CREDENTIALS}" ]; then
    SERVER_CREDENTIALS="--credentials ${SERVER_CREDENTIALS}"
fi

BIND_ADDRESS="$(ip addr | grep -oE "${BIND_PREFIX}[0-9:]+")"
"${SCRIPT_DIR}"/coap_server.py --bind "[${BIND_ADDRESS}]" ${SERVER_CREDENTIALS} \
    "${DATABASE_FILE}" \
    "${DATA_FORMAT}"
