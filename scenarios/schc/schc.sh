# schc.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

if [ -n "${SCHC_IP_ADDR}" ] && [ -n "${SCHC_DEV_ADDR}" ]; then
    NORTH_IFACE="${NORTH_IFACE:-tun0}"

    # find wpan-simulation interface within docker
    if [ -n "${WPAN_SIMULATION_PREFIX}" ]; then
        SOUTH_IFACE="$(ip addr | awk -v wpan_prefix="${WPAN_SIMULATION_PREFIX}" ' \
            BEGIN { FS=":" } \
            $0 ~ /^[0-9]+:\s+([^:]+):/ { iface=$2 } \
            $0 ~ wpan_prefix { print iface }' | xargs echo)"
    elif [ $(ip link | grep -E '^[0-9]+:\s+[^:]+:' | wc -l) -eq 2 ]; then
        SOUTH_IFACE=$(ip link | grep -Eo '^[0-9]+:\s+[^:]+:' | \
            grep -Ev '^[0-9]+:\s+lo:' | sed -E "s/^[0-9]+:\s+([^:]+):/\1/")
    else
        echo "Unable to find south interface" >&2
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

    "${SCHC_DIR}"/schc.py --north "${NORTH_IFACE}" ${ADDITIONAL_SCHC_ARGS} \
        "${SOUTH_IFACE}" "${SCHC_DEV_ADDR}" "${SCHC_DIR}"/"${SCHC_RULES}" \
        --ipv6-address "${SCHC_IP_ADDR}" \
        > "${SCHC_LOGFILE}" 2> "${SCHC_LOGFILE%.log}.stderr.log" \
        &
    SCHC_PID="$!"

    # wait for north interface to be initialized
    while ! ip addr show dev "${NORTH_IFACE}"; do
        sleep 1
    done
fi

