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
    BLOCK_SIZE_LOG="_b${BLOCK_SIZE}"
    BLOCK_SIZE="-b ${BLOCK_SIZE}"
fi

if [ -n "${PROXY}" ]; then
    PROXY="-p ${PROXY}"
fi

if [ -n "${CLIENT_CREDENTIALS}" ] && [ -z "${SECURITY}" ]; then
    echo "Credentials provided but no security mode" >&2
    exit 1
fi

if [ "${SECURITY}" = "dtls" ]; then
    if [ -z "${CLIENT_CREDENTIALS}" ]; then
        echo "DTLS configured as security but no credentials provided" >&2
        exit 1
    fi
    NETWORK_SCENARIO="$(echo "${NETWORK_SCENARIO}" | sed 's/coap/coaps/g')"
    SECURITY="-s ${SECURITY}"
    CLIENT_CREDENTIALS="--credentials ${CLIENT_CREDENTIALS}"
elif [ "${SECURITY}" = "oscore" ] || [ "${SECURITY}" = "oscore-base" ]; then
    if [ -z "${CLIENT_CREDENTIALS}" ]; then
        echo "OSCORE configured as security but no credentials provided" >&2
        exit 1
    fi
    if [ "${SECURITY}" = "oscore" ] && [ -n "${PROXY}" ] && [ -z "${CLIENT_PROXY_CREDENTIALS}" ]; then
        echo "OSCORE-capable proxy configured as security but no proxy credentials provided" >&2
        exit 1
    fi
    NETWORK_SCENARIO="$(echo "${NETWORK_SCENARIO}" | sed "s/coap/${SECURITY}/g")"
    if [ "${SECURITY}" = "oscore-base" ]; then
        SECURITY="-c -s oscore"
    else
        SECURITY="-r -s ${SECURITY}"
    fi
    CLIENT_CREDENTIALS="--credentials ${CLIENT_CREDENTIALS}"
    if [ -n "${PROXY}" ] && [ -n "${CLIENT_PROXY_CREDENTIALS}" ]; then
        CLIENT_PROXY_CREDENTIALS="--proxy-credentials ${CLIENT_PROXY_CREDENTIALS}"
    fi
    cp -r "${SCRIPT_DIR}"/creds/oscore /creds/
    chown -R root: /creds/oscore
fi

if [ -n "${SCHC_RULES_MODE}" ]; then
    SCHC_RULES_LOG="-${SCHC_RULES_MODE}"
fi

LOGFILE="/dumps/${NETWORK_SCENARIO}${SCHC_RULES_LOG}_${DATA_FORMAT_LOG}_${DNS_FORMAT_LOG}${BLOCK_SIZE_LOG}.client.log"

ADDITIONAL_SCHC_ARGS="--client"
SCHC_DIR="${SCRIPT_DIR}/../schc"
source "${SCHC_DIR}/schc.sh"

if [ -n "${SCHC_IP_ADDR}" ]; then
    BIND_ADDR=$(echo "${SCHC_IP_ADDR}" | sed 's#/[0-9]\+$##')
    BIND_PORT=45575

    # bind to fixed port for DEV_PORT compression
    BIND="--bind [${BIND_ADDR}]:${BIND_PORT}"
fi

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

"${SCRIPT_DIR}"/coap_client.py ${BIND} ${BLOCK_SIZE} \
    ${PROXY} ${SECURITY} ${CLIENT_CREDENTIALS} ${CLIENT_PROXY_CREDENTIALS} \
    "${DATABASE_URI}" \
    "${DATA_FORMAT}" \
    "${DNS_FORMAT}" \
    "${COAP_SERVER}" \
    "${DNS_SERVER}" \
    > "${LOGFILE}" 2> "${LOGFILE%.log}.stderr.log"
ERROR="$?"
exit "${ERROR}"
