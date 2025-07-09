FROM alpine:3.22

ARG HOST_UID
ARG HOST_GID
RUN addgroup -S wireshark && adduser -Ds /bin/sh user -G wireshark -u "$HOST_UID" -g "$HOST_GID"

RUN apk --update --no-cache add tcpdump libcap-setcap

RUN setcap cap_net_raw,cap_net_admin+eip /usr/bin/tcpdump
RUN chown root:wireshark /usr/bin/tcpdump && chmod u+s /usr/bin/tcpdump && chmod o-rx /usr/bin/tcpdump

