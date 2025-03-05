FROM alpine:3.21

ARG HOST_UID
ARG HOST_GID
RUN addgroup -S wireshark && adduser -Ds /bin/sh user -G wireshark -u "$HOST_UID" -g "$HOST_GID"

RUN apk --update --no-cache add tshark libcap-setcap

RUN setcap cap_net_raw,cap_net_admin+eip /usr/bin/dumpcap
RUN chown root:wireshark /usr/bin/dumpcap && chmod u+s /usr/bin/dumpcap && chmod o-rx /usr/bin/dumpcap

