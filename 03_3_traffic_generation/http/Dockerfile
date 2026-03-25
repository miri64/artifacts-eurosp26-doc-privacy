# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

FROM python:3.13.5-alpine3.22 AS base

WORKDIR /app

ARG HOST_UID
ARG HOST_GID
RUN adduser -Ds /bin/sh user -u "${HOST_UID:-1000}" -g "${HOST_GID:-1000}"

FROM base AS http-base
RUN apk --update --no-cache add postgresql-dev

COPY requirements.txt ./
RUN pip --no-cache-dir install --upgrade uv
RUN uv pip --no-cache-dir install --system --upgrade -r requirements.txt
