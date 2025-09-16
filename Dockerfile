# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

FROM python:3.12.11-bookworm

WORKDIR /app

ARG HOST_UID
ARG HOST_GID
RUN addgroup --gid "$HOST_GID" user || true  # just use group if it already exists
RUN adduser --disabled-password --home /home/user/ --shell /bin/sh user --uid "$HOST_UID" --gid "$HOST_GID"

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ gfortran hyperfine libopenblas-dev liblapack-dev parallel pigz pkg-config \
    texlive-full tmux tshark

COPY requirements.txt ./
RUN pip --no-cache-dir install --upgrade uv
RUN uv pip --no-cache-dir install --system --upgrade -r requirements.txt

COPY wireshark-cfg/ /home/user/.config/wireshark/
