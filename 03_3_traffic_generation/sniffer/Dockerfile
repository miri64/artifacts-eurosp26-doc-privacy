# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

FROM alpine:3.22

ARG HOST_UID
ARG HOST_GID
RUN addgroup -S wireshark && adduser -Ds /bin/sh user -G wireshark -u "${HOST_UID:-1000}" -g "${HOST_GID:-1000}"

RUN apk --update --no-cache add tcpdump libcap-setcap

RUN setcap cap_net_raw,cap_net_admin+eip /usr/bin/tcpdump
RUN chown root:wireshark /usr/bin/tcpdump && chmod u+s /usr/bin/tcpdump && chmod o-rx /usr/bin/tcpdump

