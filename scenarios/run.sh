#! /bin/bash
#
# run.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

SCRIPT_DIR=$( cd -- "$( dirname -- "$(realpath "$0")" )" &> /dev/null && pwd )

export HOST_GID=$(id -g)
export HOST_UID=$(id -u)

chmod -R o+r ${SCRIPT_DIR}/database/ ${SCRIPT_DIR}/../jsons/
chmod o+x ${SCRIPT_DIR}/database/ ${SCRIPT_DIR}/../jsons/

MAIN_ENV="${SCRIPT_DIR}"/.env
DATA_ENVS=(
    "${SCRIPT_DIR}"/.json.env
    "${SCRIPT_DIR}"/.cbor.env
)
DNS_ENVS=(
    "${SCRIPT_DIR}"/.dns-msg.env
    "${SCRIPT_DIR}"/.dns-cbor.env
)
SECURITIES=(
    "transport"
    "object"
    "object-base"
    ""
)
LINK_LAYERS=(
    ""
    # "schc" 
)
PROTOCOLS=(
    "coap"
    # "https"
)
NETWORK_SETUPS=("d1" "d2" "p1" "p2")
BLOCKWISE=(
    ""
    # "block"
)

if id | grep -q "=0(root)" || id | grep -vq "docker"; then
    echo "Executing user must not be root and must be in the 'docker' group" >&2
    exit 1
fi

DOCKER_COMPOSE_PIDS=()

kill_docker() {
    for pid in ${DOCKER_COMPOSE_PIDS[@]}; do
        kill -SIGTERM "${pid}"
        tail --pid="${pid}" -f /dev/null
    done
    reset
    exit
}

trap kill_docker SIGHUP SIGTERM SIGINT SIGQUIT SIGABRT

if [ "$1" = "--build" ] || ! docker image ls | grep -q "pivot-eval/"; then
    docker system prune -f

    for l2 in "${LINK_LAYERS[@]}"; do
        PREFIX_HINT_1=6
        for prot in "${PROTOCOLS[@]}"; do
            PREFIX_HINT_2=0
            for setup in "${NETWORK_SETUPS[@]}"; do
                setup_iface=$(echo "${setup}" | sed -E -e 's/([dp])1/\1i/g' -e 's/([dp])2/\1ii/g')
                l2_iface=$(echo "${l2}" | sed -E -e 's/-//g' -e 's/schc/0/g')
                export DATABASE_BACKEND_PREFIX="fd00:${PREFIX_HINT_1}b${PREFIX_HINT_2}6::"
                export WPAN_SIMULATION_NAME="${prot}${l2}-${setup}-wpan-simulation"
                export WPAN_SIMULATION_IFACE="${prot}${l2_iface}${setup}_wpan"
                export WPAN_SIMULATION_PREFIX="fdd8:${PREFIX_HINT_1}b${PREFIX_HINT_2}6:eccc::"
                export UPSTREAM_NAME="${prot}${l2}-${setup}-upstream"
                export UPSTREAM_IFACE="${prot}${l2_iface}${setup}_upstream"
                export UPSTREAM_PREFIX="fdd8:${PREFIX_HINT_1}b${PREFIX_HINT_2}6:ecc0::"
                COMPOSE_BAKE=true DATA_FORMAT=application/cbor DNS_FORMAT=application/dns+cbor \
                    docker compose --env-file "${MAIN_ENV}" \
                        ${ADDITIONAL_OPTS} \
                        -f "${SCRIPT_DIR}/docker-compose-${prot}${l2}-${setup}.yaml" build
                PREFIX_HINT_2=$(( PREFIX_HINT_2 + 1 ))
            done
            PREFIX_HINT_1=$(( PREFIX_HINT_1 + 1 ))
        done
    done

    docker image prune -f
fi 

for data_env in "${DATA_ENVS[@]}"; do
    for dns_env in "${DNS_ENVS[@]}"; do
        for sec in "${SECURITIES[@]}"; do
            for l2 in "${LINK_LAYERS[@]}"; do
                PREFIX_HINT_1=6
                for prot in "${PROTOCOLS[@]}"; do
                    if [ "$prot" != "coap" -a "$sec" != "transport" ]; then
                        continue
                    fi
                    for block in "${BLOCKWISE}"; do
                        PREFIX_HINT_2=0
                        unset DOCKER_COMPOSE_PIDS
                        for setup in "${NETWORK_SETUPS[@]}"; do
                            setup_iface=$(echo "${setup}" | sed -E -e 's/([dp])1/\1i/g' -e 's/([dp])2/\1ii/g')
                            l2_iface=$(echo "${l2}" | sed -E -e 's/-//g' -e 's/schc/0/g')
                            export DATABASE_BACKEND_PREFIX="fd00:${PREFIX_HINT_1}b${PREFIX_HINT_2}6::"
                            export WPAN_SIMULATION_NAME="${prot}${l2}-${setup}-wpan-simulation"
                            export WPAN_SIMULATION_IFACE="${prot}${l2_iface}${setup}_wpan"
                            export WPAN_SIMULATION_PREFIX="fdd8:${PREFIX_HINT_1}b${PREFIX_HINT_2}6:eccc::"
                            export UPSTREAM_NAME="${prot}${l2}-${setup}-upstream"
                            export UPSTREAM_IFACE="${prot}${l2_iface}${setup}_upstream"
                            export UPSTREAM_PREFIX="fdd8:${PREFIX_HINT_1}b${PREFIX_HINT_2}6:ecc0::"
                            ADDITIONAL_OPTS=""
                            
                            if [ "$prot" != "coap" -a -n "$block" ]; then
                                continue
                            fi
                            if [ "${sec}" = "transport" ]; then
                                ADDITIONAL_OPTS="${ADDITIONAL_OPTS} --env-file "${SCRIPT_DIR}"/.dtls.env"
                            elif [ "${sec}" = "object" ]; then
                                ADDITIONAL_OPTS="${ADDITIONAL_OPTS} --env-file "${SCRIPT_DIR}"/.oscore.env"
                            elif [ "${sec}" = "object-base" ]; then
                                ADDITIONAL_OPTS="${ADDITIONAL_OPTS} --env-file "${SCRIPT_DIR}"/.oscore-base.env"
                            elif [ -n "${sec}" ]; then
                                echo "Unexpected security mode \"${sec}\"!" >&1
                                continue
                            fi
                            if [ "${block}" = "block" ]; then
                                ADDITIONAL_OPTS="${ADDITIONAL_OPTS} --env-file "${SCRIPT_DIR}"/.block.env"
                            fi
                            docker compose --env-file "${MAIN_ENV}" \
                                ${ADDITIONAL_OPTS} \
                                --env-file "${data_env}" --env-file "${dns_env}" \
                                -f "${SCRIPT_DIR}/docker-compose-${prot}${l2}-${setup}.yaml" up \
                                    --abort-on-container-exit &
                            DOCKER_COMPOSE_PIDS+=("$!")
                            PREFIX_HINT_2=$(( PREFIX_HINT_2 + 1 ))
                        done
                        for pid in ${DOCKER_COMPOSE_PIDS[@]}; do
                            tail --pid="${pid}" -f /dev/null
                        done
                        PREFIX_HINT_1=$(( PREFIX_HINT_1 + 1 ))
                    done
                done
            done
        done
    done
done
