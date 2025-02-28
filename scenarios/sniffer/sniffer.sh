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
fi

su - user -c "\
   /usr/bin/tshark \
   -i '${SNIFFER_IFACE}' \
   -f '${SNIFFER_FILTER}' \
   -w '/dumps/${NETWORK_SCENARIO}_${DATA_FORMAT}_${DNS_FORMAT}${BLOCK_SIZE}.${SNIFFER_IFACE}.pcapng' \
"
