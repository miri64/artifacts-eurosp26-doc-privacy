#! /bin/bash
#
# coap_server.sh
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.
#

SCRIPT_DIR=$( cd -- "$( dirname -- "$(realpath "$0")" )" &> /dev/null && pwd )

export HOST_GID=$(id | sed -E 's/.*gid=([0-9]+).*$/\1/')
export HOST_UID=$(id | sed -E 's/.*uid=([0-9]+).*$/\1/')

MAIN_ENV="${SCRIPT_DIR}"/.env
DATA_ENVS=(
    "${SCRIPT_DIR}"/.json.env
    "${SCRIPT_DIR}"/.cbor.env
)
DNS_ENVS=(
    "${SCRIPT_DIR}"/.dns-msg.env
    "${SCRIPT_DIR}"/.dns-cbor.env
)
SECURITIES=("dtls")
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

for data_env in "${DATA_ENVS[@]}"; do
    for dns_env in "${DNS_ENVS[@]}"; do
        for sec in "${SECURITIES[@]}"; do
            for l2 in "${LINK_LAYERS[@]}"; do
                for prot in "${PROTOCOLS[@]}"; do
                    if [ "$prot" != "coap" -a "$sec" != "dtls" ]; then
                        continue
                    fi
                    for setup in "${NETWORK_SETUPS[@]}"; do
                        for block in "${BLOCKWISE}"; do
                            if [ "$prot" != "coap" -a -n "$block" ]; then
                                continue
                            fi
                            if [ "${sec}" = "dtls" ]; then
                                ADDITIONAL_OPTS="${ADDITIONAL_OPTS} --env-file "${SCRIPT_DIR}"/.dtls.env"
                            fi
                            if [ "${block}" = "block" ]; then
                                ADDITIONAL_OPTS="${ADDITIONAL_OPTS} --env-file "${SCRIPT_DIR}"/.block.env"
                            fi
                            docker compose --env-file "${MAIN_ENV}" \
                                ${ADDITIONAL_OPTS} \
                                --env-file "${data_env}" --env-file "${dns_env}" \
                                -f "${SCRIPT_DIR}/docker-compose-${prot}${l2}-${setup}.yaml" up \
                                    --abort-on-container-exit
                        done
                    done
                done
            done
        done
    done
done
