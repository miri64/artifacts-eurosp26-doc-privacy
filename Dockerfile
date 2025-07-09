# Dockerfile to run traffic classification on a slurm-based cluster

FROM python:3.13.5-bookworm

WORKDIR /app

ARG HOST_UID
ARG HOST_GID
RUN addgroup --gid "$HOST_GID" user
RUN adduser --disabled-password --shell /bin/sh user --uid "$HOST_UID" --gid "$HOST_GID"

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ gfortran hyperfine libopenblas-dev liblapack-dev pigz pkg-config tmux

COPY requirements.txt ./
RUN pip --no-cache-dir install --upgrade -r requirements.txt
