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

tshark -Tfields -e frame.number -e frame.protocols -e coap.code -e coap.opt.ctype -e coap.opt.block_number -e coap.opt.block_mflag -e coap.opt.block_size -r "${PCAP}"
