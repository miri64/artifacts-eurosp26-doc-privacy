FROM python:3.13.2-alpine3.21

WORKDIR /app

ARG HOST_UID
ARG HOST_GID
RUN adduser -Ds /bin/bash user -u "$HOST_UID" -g "$HOST_GID"
RUN apk --update --no-cache add autoconf automake cargo cython git pkgconf postgresql-dev postgresql-libs

COPY requirements.txt ./
RUN pip --no-cache-dir install --upgrade -r requirements.txt
