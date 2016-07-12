# Yandex.Tank
#
# VERSION 0.0.3

FROM ubuntu:xenial
MAINTAINER Alexey Lavrenuke <direvius@yandex-team.ru>

LABEL Description="Fresh Yandex.Tank from github master branch with phantom" Vendor="Yandex" Version="0.0.3"

RUN adduser  --disabled-password --gecos '' yandextank && adduser yandextank sudo && \
    export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && apt-get install software-properties-common -y && \
    add-apt-repository ppa:yandex-load/main -y && \
    apt-get update && apt-get install -y python-pip phantom phantom-ssl && \
    BUILD_DEPS="python-dev build-essential gfortran libssl-dev libffi-dev" && \
    apt-get install -y ${BUILD_DEPS} && \
    pip install --upgrade pip && \
    pip install --upgrade setuptools && \
    apt-get autoremove -y ${BUILD_DEPS} && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN pip install https://api.github.com/repos/yandex/yandex-tank/tarball/master

USER yandextank

VOLUME ["/var/loadtest"]
WORKDIR /var/loadtest
ENTRYPOINT /usr/local/bin/yandex-tank
