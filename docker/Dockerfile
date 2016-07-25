# Yandex.Tank
#
# VERSION 0.0.3

FROM ubuntu:xenial
MAINTAINER Alexey Lavrenuke <direvius@yandex-team.ru>

LABEL Description="Fresh Yandex.Tank from github master branch with phantom" Vendor="Yandex" Version="0.0.3"

RUN useradd -m -G sudo yandextank && echo yandextank:yandextank | chpasswd && \
    export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -y sudo && \
    apt-get install -y wget && \
    apt-get install software-properties-common -y && \
    add-apt-repository ppa:yandex-load/main -y && \
    apt-get update && apt-get install -y python-pip phantom phantom-ssl

ENV TELEGRAF_VERSION 0.13.1

RUN gpg --keyserver hkp://ha.pool.sks-keyservers.net --recv-keys 05CE15085FC09D18E99EFB22684A14CF2582E0C5 && \
    wget -q https://dl.influxdata.com/telegraf/releases/telegraf_${TELEGRAF_VERSION}_amd64.deb.asc && \
    wget -q https://dl.influxdata.com/telegraf/releases/telegraf_${TELEGRAF_VERSION}_amd64.deb && \
    gpg --batch --verify telegraf_${TELEGRAF_VERSION}_amd64.deb.asc telegraf_${TELEGRAF_VERSION}_amd64.deb && \
    dpkg -i telegraf_${TELEGRAF_VERSION}_amd64.deb && \
    rm -f telegraf_${TELEGRAF_VERSION}_amd64.deb*

RUN BUILD_DEPS="python-dev build-essential gfortran libssl-dev libffi-dev" && \
    apt-get install -y ${BUILD_DEPS} && \
    pip install --upgrade pip && \
    pip install --upgrade setuptools && \
    pip install https://api.github.com/repos/yandex/yandex-tank/tarball/master && \
    apt-get autoremove -y ${BUILD_DEPS} && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

USER yandextank

VOLUME ["/var/loadtest"]
WORKDIR /var/loadtest
ENTRYPOINT /usr/local/bin/yandex-tank