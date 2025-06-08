#! /bin/sh
#
# http_server.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

SCRIPT_DIR=$( cd -- "$( dirname -- "$(realpath "$0")" )" &> /dev/null && pwd )

DATA_FORMAT_LOG=$(echo "${DATA_FORMAT}" | sed -e "s#application/##g" -e 's#[/+\-]\+#_#g');
DNS_FORMAT_LOG=$(echo "${DNS_FORMAT}" | sed -e "s#application/##g" -e 's#[/+\-]\+#_#g');

if [ -n "${SERVER_CREDENTIALS}" ]; then
    SERVER_CREDENTIALS="--credentials ${SERVER_CREDENTIALS}"
fi

if [ "${SECURITY}" = "tls" ]; then
    NETWORK_SCENARIO="$(echo "${NETWORK_SCENARIO}" | sed 's/http/https/g')"
fi

LOGFILE="/dumps/${NETWORK_SCENARIO}${SCHC_RULES_LOG}_${DATA_FORMAT_LOG}_${DNS_FORMAT_LOG}${BLOCK_SIZE}.${SERVER_NAME}.log"

chown_logs() {
    chown user: "${LOGFILE}" "${LOGFILE%.log}.stderr.log"
}

trap chown_logs EXIT HUP TERM INT QUIT ABRT KILL

BIND_ADDRESS="$(ip addr | grep -oE "${BIND_PREFIX}[0-9:]+")"
"${SCRIPT_DIR}"/http_server.py --bind "[${BIND_ADDRESS}]" ${SERVER_CREDENTIALS} \
    "${DATABASE_URI}" \
    "${DATA_FORMAT}" \
    > "${LOGFILE}" 2> "${LOGFILE%.log}.stderr.log"
ERROR="$?"
exit "${ERROR}"
