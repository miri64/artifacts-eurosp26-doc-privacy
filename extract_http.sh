#! /bin/sh
#
# extract_http.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

if [ $# -ne 1 ]; then
    echo "usage: $0 <pcap file>" >&2
    exit 1
fi

PCAP="$1"

FIELDS="frame.number frame.time_epoch frame.protocols tls.record.content_type"
FIELDS="${FIELDS} tcp.analysis.acks_frame tcp.analysis.duplicate_ack_frame tcp.analysis.rto_frame tcp.reassembled_in tcp.segment"
FIELDS="${FIELDS} http2.headers.method http2.streamid http2.request_in http2.body.reassembled.in http2.headers.content_type"


echo "${FIELDS}" | \
    awk 'BEGIN {OFS="\t"} { for (i = 1; i <= NF; i++) { printf "%s%s", $i, (i < NF) ? OFS : ORS } }'
tshark -Tfields $(for field in ${FIELDS}; do printf -- "-e %s " "${field}"; done) -r "${PCAP}"
