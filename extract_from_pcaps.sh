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

    if (! echo "$PCAP" | grep -Eq ".*\.upstream.pcap.gz" || echo "${PCAP}" | grep -Eq "\<https-") && ! [ -f "${PCAP%.pcap.gz}".eth.csv.gz ]; then
        "${SCRIPT_DIR}/extract_eth.sh" "${PCAP}" | gzip > "${PCAP%.pcap.gz}".eth.csv.gz
    elif [ -f "${PCAP%.pcap.gz}".eth.csv.gz ]; then
        echo "\"${PCAP%.pcap.gz}.eth.csv.gz\" exists already" >&2
    fi
    if echo "${PCAP}" | grep -Eq "\<https-" && ! [ -f "${PCAP%.pcap.gz}".http.csv.gz ]; then
        "${SCRIPT_DIR}/extract_http.sh" "${PCAP}" | gzip > "${PCAP%.pcap.gz}".http.csv.gz
    elif echo "${PCAP}" | grep -Eq -e "-schc-" && ! echo "$PCAP" | grep -Eq ".*\.upstream.pcap.gz" && ! [ -f "${PCAP%.pcap.gz}".coap.csv.gz ]; then
        if echo "$PCAP" | grep -q "oscore"; then
            OSCORE="oscore"
        fi
        "${SCRIPT_DIR}/extract_schc.py" "${PCAP%.pcap.gz}".eth.csv.gz | \
             text2pcap -l 101 -t "%s.%f" -q - - 2>/dev/null | \
             "${SCRIPT_DIR}/extract_coap.sh" - "${OSCORE}" | gzip > "${PCAP%.pcap.gz}".coap.csv.gz
    elif ! echo "${PCAP}" | grep -Eq "\<https-" && ! [ -f "${PCAP%.pcap.gz}".coap.csv.gz ]; then
        "${SCRIPT_DIR}/extract_coap.sh" "${PCAP}" | gzip > "${PCAP%.pcap.gz}".coap.csv.gz
    elif [ -f "${PCAP%.pcap.gz}".http.csv.gz ]; then
        echo "\"${PCAP%.pcap.gz}.http.csv.gz\" exists already" >&2
    elif [ -f "${PCAP%.pcap.gz}".coap.csv.gz ]; then
        echo "\"${PCAP%.pcap.gz}.coap.csv.gz\" exists already" >&2
    fi
}

export -f extract_from_pcap
export SCRIPT_DIR

find "${OUTPUT_DATASET}" -name "*.wpan.pcap.gz" -o -name "*.upstream.pcap.gz" | \
    parallel --progress -j"${PROCS}" extract_from_pcap
