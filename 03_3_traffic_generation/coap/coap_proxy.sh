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
    cp -r "${SCRIPT_DIR}"/creds/oscore /creds/
    chown -R root: /creds/oscore
fi

if [ "${SECURITY}" = "dtls" ]; then
    NETWORK_SCENARIO="$(echo "${NETWORK_SCENARIO}" | sed 's/coap/coaps/g')"
elif [ "${SECURITY}" = "oscore" ]; then
    NETWORK_SCENARIO="$(echo "${NETWORK_SCENARIO}" | sed 's/coap/oscore/g')"
elif [ "${SECURITY}" = "oscore-base" ]; then
    NETWORK_SCENARIO="$(echo "${NETWORK_SCENARIO}" | sed 's/coap/oscore-base/g')"
fi

if [ -n "${SCHC_RULES_MODE}" ]; then
    SCHC_RULES_LOG="-${SCHC_RULES_MODE}"
fi

LOGFILE="/dumps/${NETWORK_SCENARIO}${SCHC_RULES_LOG}_${DATA_FORMAT}_${DNS_FORMAT}${BLOCK_SIZE}.proxy.log"

SCHC_DIR="${SCRIPT_DIR}/../schc"
source "${SCHC_DIR}/schc.sh"

if [ -n "${NORTH_IFACE}" ]; then
    su - user -c "/usr/bin/tshark -i '${NORTH_IFACE}' -w '${LOGFILE%.log}.pcapng'" &
    TSHARK_PID=$!
fi

chown_logs() {
    if [ -n "${SCHC_PID}" ]; then
        kill "${SCHC_PID}"
        chown user: "${SCHC_LOGFILE}" "${SCHC_LOGFILE%.log}.stderr.log" "${ROUTE_FILE}"
    fi
    if [ -n "${TSHARK_PID}" ]; then
        kill "${TSHARK_PID}"
    fi
    chown user: "${LOGFILE}" "${LOGFILE%.log}.stderr.log"
}

trap chown_logs EXIT HUP TERM INT QUIT ABRT KILL

BIND_ADDRESS="$(ip addr | grep -oE "${BIND_PREFIX}[0-9:]+")"
"${SCRIPT_DIR}"/coap_proxy.py --bind "[${BIND_ADDRESS}]" ${PROXY_CREDENTIALS} \
    "${DATABASE_URI}" \
    > "${LOGFILE}" 2> "${LOGFILE%.log}.stderr.log"
ERROR="$?"
exit "${ERROR}"
