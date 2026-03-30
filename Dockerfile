# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

FROM python:3.12-trixie

WORKDIR /app

ARG HOST_UID
ARG HOST_GID
RUN addgroup --gid "$HOST_GID" user || true  # just use group if it already exists
RUN addgroup wireshark || true  # just use group if it already exists
RUN addgroup docker || true  # just use group if it already exists
RUN adduser --disabled-password --home /home/user/ --shell /bin/bash user --uid "$HOST_UID" --gid "$HOST_GID" && \
    usermod -a -G wireshark user && usermod -a -G docker user && chown -R user: /home/user

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl dnsutils gawk gcc g++ gfortran hyperfine \
    libopenblas-dev liblapack-dev parallel pigz pkg-config \
    poppler-utils texlive-full tmux tshark

RUN install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc && \
    chmod a+r /etc/apt/keyrings/docker.asc && \
    echo "Types: deb\nURIs: https://download.docker.com/linux/debian\nSuites: $(. /etc/os-release && echo "$VERSION_CODENAME")\nComponents: stable\nSigned-By: /etc/apt/keyrings/docker.asc\n" \
    > /etc/apt/sources.list.d/docker.sources && cat /etc/apt/sources.list.d/docker.sources
RUN apt-get update && apt-get install -y --no-install-recommends docker-compose-plugin docker-ce-rootless-extras docker-ce docker-ce-cli containerd.io docker-buildx-plugin

RUN setcap cap_net_raw,cap_net_admin+eip /usr/bin/dumpcap && \
   chown root:wireshark /usr/bin/dumpcap && chmod u+s /usr/bin/dumpcap && chmod o-rx /usr/bin/dumpcap

COPY requirements.txt ./
RUN pip --no-cache-dir install --upgrade uv
RUN uv pip --no-cache-dir install --system --upgrade -r requirements.txt

COPY wireshark-cfg/ /home/user/.config/wireshark/
