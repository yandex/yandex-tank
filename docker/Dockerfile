# Yandex.Tank
#
# VERSION 0.0.1

FROM ubuntu:xenial
MAINTAINER Alexey Lavrenuke <direvius@yandex-team.ru>

LABEL Description="Fresh Yandex.Tank from github master branch with phantom" Vendor="Yandex" Version="0.0.1"

ENV DEBIAN_FRONTEND noninteractive

VOLUME ["/var/loadtest"]
WORKDIR /var/loadtest

RUN apt-get update && apt-get install software-properties-common -y -q && \
    add-apt-repository ppa:yandex-load/main -y && \
    apt-get update && apt-get install -y -q python-pip python-dev build-essential gfortran libssl-dev phantom phantom-ssl && \
    pip install --upgrade pip && \
    pip install --upgrade setuptools

RUN pip install https://api.github.com/repos/yandex/yandex-tank/tarball/master

ENTRYPOINT /usr/bin/yandex-tank
