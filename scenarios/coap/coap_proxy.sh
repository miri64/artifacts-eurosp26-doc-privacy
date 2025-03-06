#! /bin/sh
#
# coap_proxy.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

SCRIPT_DIR=$( cd -- "$( dirname -- "$(realpath "$0")" )" &> /dev/null && pwd )

DATA_FORMAT=$(echo "${DATA_FORMAT}" | sed -e "s#application/##g" -e 's#[/+\-]\+#_#g');
DNS_FORMAT=$(echo "${DNS_FORMAT}" | sed -e "s#application/##g" -e 's#[/+\-]\+#_#g');

if [ -n "${BLOCK_SIZE}" ]; then
    BLOCK_SIZE="_b${BLOCK_SIZE}"
fi

if [ -n "${PROXY_CREDENTIALS}" ]; then
    PROXY_CREDENTIALS="--credentials ${PROXY_CREDENTIALS}"
fi

if [ "${SECURITY}" = "dtls" ]; then
    NETWORK_SCENARIO="$(echo "${NETWORK_SCENARIO}" | sed 's/coap/coaps/g')"
fi

LOGFILE="/dumps/${NETWORK_SCENARIO}_${DATA_FORMAT}_${DNS_FORMAT}${BLOCK_SIZE}.proxy.log"

BIND_ADDRESS="$(ip addr | grep -oE "${BIND_PREFIX}[0-9:]+")"
"${SCRIPT_DIR}"/coap_proxy.py --bind "[${BIND_ADDRESS}]" ${PROXY_CREDENTIALS} \
    "${DATABASE_FILE}" \
    > "${LOGFILE}" 2> "${LOGFILE%.log}.stderr.log"
chown user: "${LOGFILE}" "${LOGFILE%.log}.stderr.log"
