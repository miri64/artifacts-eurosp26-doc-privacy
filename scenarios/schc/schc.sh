# schc.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

if [ -n "${SCHC_IP_ADDR}" ]; then
    if [ -z "${SERVER_NAME}" ]; then
        HOST="client"
    else
        HOST="${SERVER_NAME}"
    fi

    NORTH_IFACE="${NORTH_IFACE:-tun0}"
    ROUTE_FILE="${ROUTE_FILE:-${LOGFILE%".${HOST}.log"}.routes.txt}"

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
        ADDITIONAL_SCHC_ARGS="${ADDITIONAL_SCHC_ARGS} --pdu ${SCHC_PDU}"
    fi
    if [ -n "${SCHC_DUTY_CYCLE}" ]; then
        ADDITIONAL_SCHC_ARGS="${ADDITIONAL_SCHC_ARGS} --duty-cycle ${SCHC_DUTY_CYCLE}"
    fi
    if [ -n "${SCHC_ETHERTYPE}" ]; then
        ADDITIONAL_SCHC_ARGS="${ADDITIONAL_SCHC_ARGS} --ethertype ${SCHC_ETHERTYPE}"
    fi
    SCHC_LOGFILE="${LOGFILE%.log}.schc.log"

    if [ "${SCHC_RULES_MODE}" = "peer-based" ]; then
        if [ -z "${SERVER_NAME}" ]; then
            if [ "${COAP_SERVER}" = "${DNS_SERVER}" ]; then
                SCHC_RULES="server=${SCHC_DIR}/${NETWORK_SCENARIO}-rules.json"
            else
                SCHC_RULES="${COAP_SERVER}=${SCHC_DIR}/${NETWORK_SCENARIO}-rules-${COAP_SERVER}.json"
                SCHC_RULES="${SCHC_RULES} ${DNS_SERVER}=${SCHC_DIR}/${NETWORK_SCENARIO}-rules-${DNS_SERVER}.json"
            fi
        else
            SCHC_RULES="${SERVER_NAME}=${SCHC_DIR}/${NETWORK_SCENARIO}-rules-${SERVER_NAME}.json"
        fi
    else
        SCHC_RULES="${SCHC_DIR}/${NETWORK_SCENARIO}-rules.json"
    fi

    if [ "${SERVER_NAME}" = "server" ] || [ "${SERVER_NAME}" = "coap-server" ] || [ "${SERVER_NAME}" = "proxy" ]; then
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
    echo "${HOST} ${SCHC_IP_ADDR} ${SCHC_DEV_ADDR}" >> "${ROUTE_FILE}"

    SERVER_NAME="${SERVER_NAME}" "${SCHC_DIR}"/schc.py \
        --north "${NORTH_IFACE}" ${ADDITIONAL_SCHC_ARGS} \
        "${SOUTH_IFACE}" ${SCHC_PEER_ADDRS} \
        --rule-config ${SCHC_RULES} \
        --ipv6-address "${SCHC_IP_ADDR}" --route-file "${ROUTE_FILE}" \
        > "${SCHC_LOGFILE}" 2> "${SCHC_LOGFILE%.log}.stderr.log" \
        &
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

