#! /bin/sh
#
# sniffer.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

DATA_FORMAT=$(echo "${DATA_FORMAT}" | sed -e "s#application/##g" -e 's#[/+\-]\+#_#g');
DNS_FORMAT=$(echo "${DNS_FORMAT}" | sed -e "s#application/##g" -e 's#[/+\-]\+#_#g');

if [ -n "${BLOCK_SIZE}" ]; then
    BLOCK_SIZE="_b${BLOCK_SIZE}"
fi

if [ "${SECURITY}" = "dtls" ]; then
    NETWORK_SCENARIO="$(echo "${NETWORK_SCENARIO}" | sed 's/coap/coaps/g')"
elif [ "${SECURITY}" = "oscore" ]; then
    NETWORK_SCENARIO="$(echo "${NETWORK_SCENARIO}" | sed 's/coap/oscore/g')"
elif [ "${SECURITY}" = "oscore-base" ]; then
    NETWORK_SCENARIO="$(echo "${NETWORK_SCENARIO}" | sed 's/coap/oscore-base/g')"
elif [ "${SECURITY}" = "tls" ]; then
    NETWORK_SCENARIO="$(echo "${NETWORK_SCENARIO}" | sed 's/http/https/g')"
fi

if [ -n "${SCHC_RULES_MODE}" ]; then
    SCHC_RULES_LOG="-${SCHC_RULES_MODE}"
fi

su - user -c "\
   /usr/bin/tshark \
   -i '${SNIFFER_IFACE}' \
   -f '${SNIFFER_FILTER}' \
   -w '/dumps/${NETWORK_SCENARIO}${SCHC_RULES_LOG}_${DATA_FORMAT}_${DNS_FORMAT}${BLOCK_SIZE}.${SNIFFER_LOGNAME}.pcapng' \
"
