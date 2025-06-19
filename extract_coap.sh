#! /bin/sh
#
# extract_coap.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

if [ $# -ne 1 ] && [ $# -ne 2 ]; then
    echo "usage: $0 <pcap file|-> [oscore]" >&2
    exit 1
fi

PCAP="$1"

FIELDS="frame.number frame.time_epoch frame.protocols dtls.record.content_type"
FIELDS="${FIELDS} coap.code coap.request_first_in coap.mid coap.token coap.opt.ctype coap.opt.block_number coap.opt.block_mflag coap.opt.block_size coap.block coap.block.reassembled.in"

if echo "$PCAP" | grep -q "oscore" || [ "$2" = "oscore" ]; then
    FIELDS="${FIELDS} oscore.code oscore.opt.ctype oscore.opt.block_number oscore.opt.block_mflag oscore.opt.block_size"
fi


echo "${FIELDS}" | \
    awk 'BEGIN {OFS="\t"} { for (i = 1; i <= NF; i++) { printf "%s%s", $i, (i < NF) ? OFS : ORS } }'
tshark -Tfields $(for field in ${FIELDS}; do printf -- "-e %s " "${field}"; done) -r "${PCAP}"
