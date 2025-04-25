#!/usr/bin/env bash
#
# extract_from_pcaps.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

SCRIPT_DIR=$( cd -- "$( dirname -- "$(realpath "$0")" )" &> /dev/null && pwd )
PROCS=$(grep -c '^processor' /proc/cpuinfo)
if [ $PROCS -gt 64 ]; then
    # leave some resources to collegues ;-)
    PROCS=$(( (PROCS * 3) / 4))
fi
OUTPUT_DATASET="${OUTPUT_DATASET:-${SCRIPT_DIR}/output_dataset}"


extract_from_pcap() {
    PCAP="$1"

    if ! echo "$PCAP" | grep -Eq ".*\.upstream.pcapng"; then
        "${SCRIPT_DIR}/extract_eth.sh" "${PCAP}" > "${PCAP%.pcapng}".eth.csv
    fi
    "${SCRIPT_DIR}/extract_coap.sh" "${PCAP}" > "${PCAP%.pcapng}".coap.csv
}

export -f extract_from_pcap
export SCRIPT_DIR

find "${OUTPUT_DATASET}" -name "*.wpan.pcapng" -o -name "*.upstream.pcapng" |
    parallel -j"${PROCS}" extract_from_pcap
