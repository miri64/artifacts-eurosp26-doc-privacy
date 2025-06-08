#! /bin/sh
#
# http_proxy.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

SCRIPT_DIR=$( cd -- "$( dirname -- "$(realpath "$0")" )" &> /dev/null && pwd )

DATA_FORMAT=$(echo "${DATA_FORMAT}" | sed -e "s#application/##g" -e 's#[/+\-]\+#_#g');
DNS_FORMAT=$(echo "${DNS_FORMAT}" | sed -e "s#application/##g" -e 's#[/+\-]\+#_#g');

if [ -n "${PROXY_CREDENTIALS}" ]; then
    PROXY_CREDENTIALS="--credentials ${PROXY_CREDENTIALS}"
fi

if [ "${SECURITY}" = "tls" ]; then
    NETWORK_SCENARIO="$(echo "${NETWORK_SCENARIO}" | sed 's/http/https/g')"
fi

LOGFILE="/dumps/${NETWORK_SCENARIO}${SCHC_RULES_LOG}_${DATA_FORMAT}_${DNS_FORMAT}${BLOCK_SIZE}.proxy.log"

chown_logs() {
    chown user: "${LOGFILE}" "${LOGFILE%.log}.stderr.log"
}

trap chown_logs EXIT HUP TERM INT QUIT ABRT KILL

BIND_ADDRESS="$(ip addr | grep -oE "${BIND_PREFIX}[0-9:]+")"
"${SCRIPT_DIR}"/http_proxy.py --bind "[${BIND_ADDRESS}]" ${PROXY_CREDENTIALS} \
    "${DATABASE_URI}" \
    > "${LOGFILE}" 2> "${LOGFILE%.log}.stderr.log"
ERROR="$?"
exit "${ERROR}"
