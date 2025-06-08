#! /bin/bash
#
# run.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

SCRIPT_DIR=$( cd -- "$( dirname -- "$(realpath "$0")" )" &> /dev/null && pwd )

if [ $# -eq 1 ]; then
    case $1 in
      coap|coaps|oscore|oscore-base|https) PROTOCOL="$1" ;;
      --build) ;;
      *)  echo "usage: $0 [coap|coaps|oscore|oscore-base|https]"; exit 1 ;;
    esac
fi

export HOST_GID=$(id -g)
export HOST_UID=$(id -u)

git -C "${SCRIPT_DIR}/../" submodule update --init --recursive
chmod -R o+r ${SCRIPT_DIR}/database/ ${SCRIPT_DIR}/../jsons/
chmod o+x ${SCRIPT_DIR}/database/ ${SCRIPT_DIR}/../jsons/

if ! ls ${SCRIPT_DIR}/../jsons/*.sqlite3 &> /dev/null; then
    echo "No base database found!" >&2
    exit 1
fi

declare -A PREFIX_HINT_1_START=(["coap"]=6, ["http"]=7)

MAIN_ENV="${SCRIPT_DIR}"/.env
DATA_ENVS=(
    "${SCRIPT_DIR}"/.json.env
    "${SCRIPT_DIR}"/.cbor.env
)
DNS_ENVS=(
    "${SCRIPT_DIR}"/.dns-msg.env
    "${SCRIPT_DIR}"/.dns-cbor.env
)
if [ -z "${PROTOCOL}" ]; then
    SECURITIES=(
        "transport"
        "object"
        "object-base"
        ""
    )
    PROTOCOLS=(
        "coap"
        "http"
    )
elif [ "${PROTOCOL}" = "coap" ]; then
    SECURITIES=("")
    PROTOCOLS=("coap")
elif [ "${PROTOCOL}" = "coaps" ]; then
    SECURITIES=("transport")
    PROTOCOLS=("coap")
elif [ "${PROTOCOL}" = "oscore" ]; then
    SECURITIES=("object")
    PROTOCOLS=("coap")
elif [ "${PROTOCOL}" = "oscore-base" ]; then
    SECURITIES=("object-base")
    PROTOCOLS=("coap")
elif [ "${PROTOCOL}" = "https" ]; then
    SECURITIES=("transport")
    PROTOCOLS=("http")
fi
LINK_LAYERS=(
    ""
    "schc" 
)
LINK_LAYER_MODE=(
    ""
    "peer"
    "min"
)
NETWORK_SETUPS=("d1" "d2" "p1" "p2")
BLOCKWISE=(
    ""
    "block"
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

trap kill_docker HUP TERM INT QUIT ABRT

if [ "$1" = "--build" ] || ! docker image ls | grep -q "pivot-eval/"; then
    docker system prune -f

    PREFIX_HINT_1="${PREFIX_HINT_1_START[${PROTOCOLS[0]}]}"
    for prot in "${PROTOCOLS[@]}"; do
        PREFIX_HINT_2=0
        for setup in "${NETWORK_SETUPS[@]}"; do
            for l2 in "${LINK_LAYERS[@]}"; do
                for l2_mode in "${LINK_LAYER_MODE[@]}"; do
                    ADDITIONAL_OPTS=""

                    if [[ "${l2}" = "schc" && ( -z "${sec}" || "${prot}" == "http" ) ]]; then
                        PREFIX_HINT_2=$(( PREFIX_HINT_2 + 1 ))
                        continue
                    elif [[ "${l2}" != "schc" && -n "${l2_mode}" ]]; then
                        PREFIX_HINT_2=$(( PREFIX_HINT_2 + 1 ))
                        continue
                    elif [[ "${l2}" = "schc" && -n "${l2_mode}" &&
                          "${setup}" != "d2" && ! (
                            "${sec}" = "object-base" && "${setup}" = "p2"
                          )
                    ]]; then
                        PREFIX_HINT_2=$(( PREFIX_HINT_2 + 1 ))
                        continue
                    fi

                    l2_iface=$(echo "${l2}${l2_mode}" | sed -E -e 's/-//g' -e 's/schc/0/g' -e 's/peer/1/' -e 's/min/2/')
                    if [ -n "${l2}" ]; then
                        l2_dash="-${l2}"
                        l2_name="-${l2}"
                        ADDITIONAL_OPTS="${ADDITIONAL_OPTS} --env-file "${SCRIPT_DIR}"/.${l2}.env"
                        if [ -n "${l2_mode}" ]; then
                            l2_name="${l2_name}-${l2_mode}"
                        fi
                    fi
                    if [ "${prot}" == "http" ] && [ "${sec}" == "transport" ]; then
                        ADDITIONAL_OPTS="${ADDITIONAL_OPTS} --env-file "${SCRIPT_DIR}"/.tls.env"
                    fi
                    PREFIX_HINT_1_HEX="$(printf "%x" "${PREFIX_HINT_1}")"
                    PREFIX_HINT_2_HEX="$(printf "%02x" "${PREFIX_HINT_2}")"
                    export DATABASE_BACKEND_PREFIX="fd00:${PREFIX_HINT_1_HEX}b${PREFIX_HINT_2_HEX}::"
                    export WPAN_SIMULATION_NAME="${prot}${l2_name}-${setup}-wpan-simulation"
                    export WPAN_SIMULATION_IFACE="${prot}${l2_iface}${setup}_wpan"
                    export WPAN_SIMULATION_PREFIX="fdd8:${PREFIX_HINT_1_HEX}b${PREFIX_HINT_2_HEX}:eccc::"
                    export UPSTREAM_NAME="${prot}${l2_name}-${setup}-upstream"
                    export UPSTREAM_IFACE="${prot}${l2_iface}${setup}_ups"
                    export UPSTREAM_PREFIX="fdd8:${PREFIX_HINT_1_HEX}b${PREFIX_HINT_2_HEX}:ecc0::"

                    COMPOSE_BAKE=true DATA_FORMAT=application/cbor DNS_FORMAT=application/dns+cbor \
                        docker compose -p "${prot}${l2_name}-${setup}" --env-file "${MAIN_ENV}" \
                            ${ADDITIONAL_OPTS} \
                            -f "${SCRIPT_DIR}/docker-compose-${prot}${l2_dash}-${setup}.yaml" build
                    PREFIX_HINT_2=$(( PREFIX_HINT_2 + 1 ))
                    unset l2_dash
                    unset l2_name
                    unset l2_iface
                done
            done
        done
        PREFIX_HINT_1=$(( PREFIX_HINT_1 + 1 ))
    done

    docker image prune -f
fi 

for data_env in "${DATA_ENVS[@]}"; do
    for dns_env in "${DNS_ENVS[@]}"; do
        for sec in "${SECURITIES[@]}"; do
            PREFIX_HINT_1="${PREFIX_HINT_1_START[${PROTOCOLS[0]}]}"
            for prot in "${PROTOCOLS[@]}"; do
                if [[ "$prot" != "coap" && "$sec" != "transport" ]]; then
                    continue
                fi
                ALL_SUCCESSFUL=0
                for block in "${BLOCKWISE[@]}"; do
                    while [ ${ALL_SUCCESSFUL} -eq 0 ]; do
                        PREFIX_HINT_2=0
                        unset DOCKER_COMPOSE_PIDS
                        for setup in "${NETWORK_SETUPS[@]}"; do
                            for l2 in "${LINK_LAYERS[@]}"; do
                                for l2_mode in "${LINK_LAYER_MODE[@]}"; do
                                    ADDITIONAL_OPTS=""
                                    if [[ "${l2}" = "schc" && ( -z "${sec}" || "${prot}" == "http" ) ]]; then
                                        PREFIX_HINT_2=$(( PREFIX_HINT_2 + 1 ))
                                        continue
                                    elif [[ "${l2}" != "schc" && -n "${l2_mode}" ]]; then
                                        PREFIX_HINT_2=$(( PREFIX_HINT_2 + 1 ))
                                        continue
                                    elif [[ "${l2}" = "schc" && -n "${l2_mode}" &&
                                          "${setup}" != "d2" && ! (
                                            "${sec}" = "object-base" && "${setup}" = "p2" && "${l2_mode}" != "peer"
                                          )
                                    ]]; then
                                        PREFIX_HINT_2=$(( PREFIX_HINT_2 + 1 ))
                                        continue
                                    fi
                                    l2_iface=$(echo "${l2}${l2_mode}" | sed -E -e 's/-//g' -e 's/schc/0/g' -e 's/peer/1/' -e 's/min/2/')
                                    if [ -n "${l2}" ]; then
                                        l2_dash="-${l2}"
                                        l2_name="-${l2}"
                                        ADDITIONAL_OPTS="${ADDITIONAL_OPTS} --env-file "${SCRIPT_DIR}"/.${l2}.env"
                                        if [ -n "${l2_mode}" ]; then
                                            l2_name="${l2_name}-${l2_mode}"
                                        fi
                                    fi
                                    PREFIX_HINT_1_HEX="$(printf "%x" "${PREFIX_HINT_1}")"
                                    PREFIX_HINT_2_HEX="$(printf "%02x" "${PREFIX_HINT_2}")"
                                    export DATABASE_BACKEND_PREFIX="fd00:${PREFIX_HINT_1_HEX}b${PREFIX_HINT_2_HEX}::"
                                    export WPAN_SIMULATION_NAME="${prot}${l2_name}-${setup}-wpan-simulation"
                                    export WPAN_SIMULATION_IFACE="${prot}${l2_iface}${setup}_wpan"
                                    export WPAN_SIMULATION_PREFIX="fdd8:${PREFIX_HINT_1_HEX}b${PREFIX_HINT_2_HEX}:eccc::"
                                    export UPSTREAM_NAME="${prot}${l2_name}-${setup}-upstream"
                                    export UPSTREAM_IFACE="${prot}${l2_iface}${setup}_ups"
                                    export UPSTREAM_PREFIX="fdd8:${PREFIX_HINT_1_HEX}b${PREFIX_HINT_2_HEX}:ecc0::"

                                    if [ "$prot" != "coap" -a -n "$block" ]; then
                                        continue
                                    fi
                                    if [ "${sec}" = "transport" ]; then
                                        if [ "${prot}" == "http" ]; then
                                            ADDITIONAL_OPTS="${ADDITIONAL_OPTS} --env-file "${SCRIPT_DIR}"/.tls.env"
                                        elif [ "${prot}" == "coap" ]; then
                                            ADDITIONAL_OPTS="${ADDITIONAL_OPTS} --env-file "${SCRIPT_DIR}"/.dtls.env"
                                        fi
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
                                    if [ "${l2}" = "schc" ] && [ -n "${l2_mode}" ]; then
                                        ADDITIONAL_OPTS="${ADDITIONAL_OPTS} --env-file "${SCRIPT_DIR}"/.schc.${l2_mode}.env"
                                    fi
                                    source "${data_env}"
                                    source "${dns_env}"
                                    DATA_NAME="$(echo "${DATA_FORMAT}" | sed 's#application/##g')"
                                    DNS_NAME="$(echo "${DNS_FORMAT}" | sed 's#application/##g')"
                                    script -efq "${SCRIPT_DIR}/../output_dataset/docker-compose-${prot}${l2_dash}-${setup}-${sec}-${DATA_NAME}-${DNS_NAME}.log" -c \
                                    "COMPOSE_BAKE=true docker compose -p '${prot}${l2_name}-${setup}' \
                                        --env-file '${MAIN_ENV}' ${ADDITIONAL_OPTS} \
                                        --env-file '${data_env}' --env-file '${dns_env}' \
                                        -f '${SCRIPT_DIR}/docker-compose-${prot}${l2_dash}-${setup}.yaml' up \
                                            --abort-on-container-exit" &
                                    DOCKER_COMPOSE_PIDS+=("$!")
                                    PREFIX_HINT_2=$(( PREFIX_HINT_2 + 1 ))
                                    unset l2_dash
                                    unset l2_name
                                    unset l2_iface
                                done
                            done
                        done
                        ALL_SUCCESSFUL=1
                        server=$(docker ps | awk -v pattern="${prot}.*server" '$NF ~ pattern { print $NF }' | sort | head -n 1)
                        for pid in ${DOCKER_COMPOSE_PIDS[@]}; do
                            wait "${pid}"
                            RESULT=$?
                            if [ "$RESULT" -ne 0 ]; then
                                ALL_SUCCESSFUL=0
                            fi
                        done
                        # set permissions of logs
                        docker start "${server}" && \
                        docker exec "${server}" chown "${HOST_UID}:${HOST_GID}" /dumps/*.log
                        docker stop "${server}"
                    done
                done
                PREFIX_HINT_1=$(( PREFIX_HINT_1 + 1 ))
            done
        done
    done
done
