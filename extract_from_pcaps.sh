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

    if ! echo "$PCAP" | grep -Eq ".*\.upstream.pcap" && ! [ -f "${PCAP%.pcap}".eth.csv ]; then
        "${SCRIPT_DIR}/extract_eth.sh" "${PCAP}" > "${PCAP%.pcap}".eth.csv
    elif [ -f "${PCAP%.pcap}".eth.csv ]; then
        echo "\"${PCAP%.pcap}.eth.csv\" exists already" >&2
    fi
    if echo "${PCAP}" | grep -Eq "\<https-" && ! echo "$PCAP" | grep -Eq ".*\.upstream.pcap" && ! [ -f "${PCAP%.pcap}".http.csv ]; then
        "${SCRIPT_DIR}/extract_http.sh" "${PCAP}" > "${PCAP%.pcap}".http.csv
    elif echo "${PCAP}" | grep -Eq -e "-schc-" && ! echo "$PCAP" | grep -Eq ".*\.upstream.pcap" && ! [ -f "${PCAP%.pcap}".coap.csv ]; then
        if echo "$PCAP" | grep -q "oscore"; then
            OSCORE="oscore"
        fi
        "${SCRIPT_DIR}/extract_schc.py" "${PCAP%.pcap}".eth.csv | \
             text2pcap -l 101 -t "%s.%f" -q - - 2>/dev/null | \
             "${SCRIPT_DIR}/extract_coap.sh" - "${OSCORE}" > "${PCAP%.pcap}".coap.csv
    elif ! echo "${PCAP}" | grep -Eq "\<https-" && ! [ -f "${PCAP%.pcap}".coap.csv ]; then
        "${SCRIPT_DIR}/extract_coap.sh" "${PCAP}" > "${PCAP%.pcap}".coap.csv
    elif [ -f "${PCAP%.pcap}".http.csv ]; then
        echo "\"${PCAP%.pcap}.http.csv\" exists already" >&2
    elif [ -f "${PCAP%.pcap}".coap.csv ]; then
        echo "\"${PCAP%.pcap}.coap.csv\" exists already" >&2
    fi
}

export -f extract_from_pcap
export SCRIPT_DIR

find "${OUTPUT_DATASET}" -name "*.wpan.pcap" -o -name "*.upstream.pcap" | \
    parallel -j"${PROCS}" extract_from_pcap
