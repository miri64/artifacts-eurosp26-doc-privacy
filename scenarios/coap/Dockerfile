FROM python:3.13.2-alpine3.21 AS base

WORKDIR /app

ARG HOST_UID
ARG HOST_GID
RUN addgroup -S wireshark && adduser -Ds /bin/sh user -G wireshark -u "$HOST_UID" -g "$HOST_GID"

FROM base AS coap-base
RUN apk --update --no-cache add \
    autoconf automake cargo cython git linux-headers pkgconf postgresql-dev postgresql-libs \
    tshark libcap-setcap

RUN setcap cap_net_raw,cap_net_admin+eip /usr/bin/dumpcap
RUN chown root:wireshark /usr/bin/dumpcap && chmod u+s /usr/bin/dumpcap && chmod o-rx /usr/bin/dumpcap

COPY requirements.txt ./
RUN pip --no-cache-dir install --upgrade -r requirements.txt
