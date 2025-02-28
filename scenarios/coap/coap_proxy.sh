#! /bin/sh
#
# coap_proxy.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

SCRIPT_DIR=$( cd -- "$( dirname -- "$(realpath "$0")" )" &> /dev/null && pwd )

if [ -n "${PROXY_CREDENTIALS}" ]; then
    PROXY_CREDENTIALS="--credentials ${PROXY_CREDENTIALS}"
fi

BIND_ADDRESS="$(ip addr | grep -oE "${BIND_PREFIX}[0-9:]+")"
/app/coap/coap_proxy.py --bind "[${BIND_ADDRESS}]" ${PROXY_CREDENTIALS} \
    "${DATABASE_FILE}" \
