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

echo "frame.number\tframe.time_epoch\teth.payload"
tshark -Tfields -e frame.number -e frame.time_epoch -e data --disable-protocol ALL --enable-protocol eth -r "${PCAP}"