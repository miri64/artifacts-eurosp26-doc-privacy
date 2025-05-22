# schc.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

if [ -n "${SCHC_IP_ADDR}" ]; then
    NORTH_IFACE="${NORTH_IFACE:-tun0}"
    ROUTE_FILE="${ROUTE_FILE:-/schc/route/routes.txt}"


    # find wpan-simulation interface within docker
    if [ -n "${WPAN_SIMULATION_PREFIX}" ]; then
        SOUTH_IFACE="$(ip addr | awk -v wpan_prefix="${WPAN_SIMULATION_PREFIX}" ' \
            BEGIN { FS=":" } \
            $0 ~ /^[0-9]+:\s+([^:]+):/ { iface=$2 } \
            $0 ~ wpan_prefix { print iface }' | cut -d'@' -f1 | xargs echo)"
    else
        echo "Unable to find south interface. Maybe WPAN simulation prefix was not set?" >&2
        exit 1
    fi

    ADDITIONAL_SCHC_ARGS="${ADDITIONAL_SCHC_ARGS} -v"
    if [ -n "${SCHC_PDU}" ]; then
        ADDITIONAL_SCHC_ARGS="${ADDITIONAL_SCHC_ARGS} --pdu '${SCHC_PDU}'"
    fi
    if [ -n "${SCHC_DUTY_CYCLE}" ]; then
        ADDITIONAL_SCHC_ARGS="${ADDITIONAL_SCHC_ARGS} --duty-cycle '${SCHC_DUTY_CYCLE}'"
    fi
    SCHC_LOGFILE="${LOGFILE%.log}.schc.log"
    SCHC_RULES="${NETWORK_SCENARIO}-rules.json"


    if ! echo "${ADDITIONAL_SCHC_ARGS}" | grep -q -e "--client"; then
        rm -f "${ROUTE_FILE}"
    fi
    if [ -f "${ROUTE_FILE}" ]; then
        cat "${ROUTE_FILE}"
    fi
    SCHC_DEV_ADDR=$( \
        ip addr show dev "${SOUTH_IFACE}" | grep "link/ether" | awk '{print $2}' | tr -d ':' \
    )
    if [ -f "${ROUTE_FILE}" ]; then
        sed -i "#${SCHC_IP_ADDR}#d" "${ROUTE_FILE}"
    fi
    echo "${SCHC_IP_ADDR}=${SCHC_DEV_ADDR}" >> "${ROUTE_FILE}"

    "${SCHC_DIR}"/schc.py --north "${NORTH_IFACE}" ${ADDITIONAL_SCHC_ARGS} \
        "${SOUTH_IFACE}" "${SCHC_DIR}"/"${SCHC_RULES}" ${SCHC_PEER_ADDRS} \
        --ipv6-address "${SCHC_IP_ADDR}" --route-file "${ROUTE_FILE}" \
        > "${SCHC_LOGFILE}" \
        &
        # > "${SCHC_LOGFILE}" 2> "${SCHC_LOGFILE%.log}.stderr.log" \
    SCHC_PID="$!"

    # wait for north interface to be initialized
    while ! ip addr show dev "${NORTH_IFACE}" | grep -q "${SCHC_IP_ADDR}" 2> /dev/null; do
        sleep 5
        if ! ps | grep -q "^\s\+\<${SCHC_PID}\>"; then
            echo "SCHC process (PID=${SCHC_PID}) was stopped unexpectedly" >&2
            echo "================================== stdout ==================================" >&2
            cat "${SCHC_LOGFILE}" >&2
            echo "================================== stderr ==================================" >&2
            cat "${SCHC_LOGFILE%.log}.stderr.log" >&2
            exit 1
        fi
    done
fi

