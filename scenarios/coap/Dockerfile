FROM python:3.13.2-alpine3.21

WORKDIR /app

COPY requirements.txt ./

RUN adduser -Ds /bin/bash user
RUN apk --update --no-cache add autoconf automake cargo cython git pkgconf
RUN pip --no-cache-dir install --upgrade -r requirements.txt
