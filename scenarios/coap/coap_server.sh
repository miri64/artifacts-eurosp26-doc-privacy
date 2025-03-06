#! /bin/sh
#
# coap_server.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

SCRIPT_DIR=$( cd -- "$( dirname -- "$(realpath "$0")" )" &> /dev/null && pwd )

DATA_FORMAT_LOG=$(echo "${DATA_FORMAT}" | sed -e "s#application/##g" -e 's#[/+\-]\+#_#g');
DNS_FORMAT_LOG=$(echo "${DNS_FORMAT}" | sed -e "s#application/##g" -e 's#[/+\-]\+#_#g');

if [ -n "${BLOCK_SIZE}" ]; then
    BLOCK_SIZE="_b${BLOCK_SIZE}"
fi

if [ -n "${SERVER_CREDENTIALS}" ]; then
    SERVER_CREDENTIALS="--credentials ${SERVER_CREDENTIALS}"
fi

if [ "${SECURITY}" = "dtls" ]; then
    NETWORK_SCENARIO="$(echo "${NETWORK_SCENARIO}" | sed 's/coap/coaps/g')"
fi

LOGFILE="/dumps/${NETWORK_SCENARIO}_${DATA_FORMAT_LOG}_${DNS_FORMAT_LOG}${BLOCK_SIZE}.server.log"

BIND_ADDRESS="$(ip addr | grep -oE "${BIND_PREFIX}[0-9:]+")"
"${SCRIPT_DIR}"/coap_server.py --bind "[${BIND_ADDRESS}]" ${SERVER_CREDENTIALS} \
    "${DATABASE_URI}" \
    "${DATA_FORMAT}" \
    > "${LOGFILE}" 2> "${LOGFILE%.log}.stderr.log"
ERROR="$?"
chown user: "${LOGFILE}" "${LOGFILE%.log}.stderr.log"
exit "${ERROR}"
