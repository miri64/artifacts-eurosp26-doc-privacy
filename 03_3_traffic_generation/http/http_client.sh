#! /bin/sh
#
# http_client.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

SCRIPT_DIR=$( cd -- "$( dirname -- "$(realpath "$0")" )" &> /dev/null && pwd )

DATA_FORMAT_LOG=$(echo "${DATA_FORMAT}" | sed -e "s#application/##g" -e 's#[/+\-]\+#_#g');
DNS_FORMAT_LOG=$(echo "${DNS_FORMAT}" | sed -e "s#application/##g" -e 's#[/+\-]\+#_#g');

if [ -n "${PROXY}" ]; then
    PROXY="-p ${PROXY}"
fi

if [ -n "${CLIENT_CREDENTIALS}" ] && [ -z "${SECURITY}" ]; then
    echo "Credentials provided but no security mode" >&2
    exit 1
fi

if [ "${SECURITY}" = "tls" ]; then
    if [ -z "${CLIENT_CREDENTIALS}" ]; then
        echo "DTLS configured as security but no credentials provided" >&2
        exit 1
    fi
    NETWORK_SCENARIO="$(echo "${NETWORK_SCENARIO}" | sed 's/http/https/g')"
    CLIENT_CREDENTIALS="--credentials ${CLIENT_CREDENTIALS}"
fi

LOGFILE="/dumps/${NETWORK_SCENARIO}${SCHC_RULES_LOG}_${DATA_FORMAT_LOG}_${DNS_FORMAT_LOG}${BLOCK_SIZE_LOG}.client.log"

chown_logs() {
    chown user: "${LOGFILE}" "${LOGFILE%.log}.stderr.log"
}

trap chown_logs EXIT HUP TERM INT QUIT ABRT KILL

echo "$(date -R): Starting ${LOGFILE#/dumps/%.client.log}"
"${SCRIPT_DIR}"/http_client.py \
    ${PROXY} ${CLIENT_CREDENTIALS} \
    "${DATABASE_URI}" \
    "${DATA_FORMAT}" \
    "${DNS_FORMAT}" \
    "${COAP_SERVER}" \
    "${DNS_SERVER}" \
    > "${LOGFILE}" 2> "${LOGFILE%.log}.stderr.log"
ERROR="$?"
sleep 5  # wait for server/proxy to finish up there things
echo "$(date -R): Stopping ${LOGFILE#/dumps/%.client.log}"
exit "${ERROR}"
