FROM alpine:3.21

RUN addgroup -S wireshark && adduser -Ds /bin/sh user -G wireshark
RUN apk --update --no-cache add tshark libcap-setcap
RUN setcap cap_net_raw,cap_net_admin+eip /usr/bin/dumpcap
RUN chown root:wireshark /usr/bin/dumpcap && chmod u+s /usr/bin/dumpcap && chmod o-rx /usr/bin/dumpcap

