#! /bin/sh
#
# extract_eth.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

if [ $# -ne 1 ]; then
    echo "usage: $0 <pcap file>" >&2
    exit 1
fi

PCAP="$1"

FIELDS="frame.number frame.time_epoch eth.src eth.dst eth.type eth.payload"
echo "${FIELDS}" | \
    awk 'BEGIN {OFS="\t"} { for (i = 1; i <= NF; i++) { printf "%s%s", $i, (i < NF) ? OFS : ORS } }'
tshark -Tfields -e frame.number -e frame.time_epoch -e eth.src -e eth.dst -e eth.type -e data --disable-protocol ALL --enable-protocol eth -r "${PCAP}"
