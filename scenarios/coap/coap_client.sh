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
fi

LOGFILE="/dumps/${NETWORK_SCENARIO}_${DATA_FORMAT_LOG}_${DNS_FORMAT_LOG}${BLOCK_SIZE_LOG}.client.log"

/app/coap/coap_client.py ${BLOCK_SIZE} ${SECURITY} ${CLIENT_CREDENTIALS} \
    "${DATABASE_FILE}" \
    "${DATA_FORMAT}" \
    "${DNS_FORMAT}" \
    "${COAP_SERVER}" \
    "${DNS_SERVER}" \
    > "${LOGFILE}"
chown user: "${LOGFILE}"
