# Yandex.Tank
#
# VERSION 0.0.3

FROM ubuntu:xenial
MAINTAINER Alexey Lavrenuke <direvius@yandex-team.ru>
# Version for desription
ARG VERSION
# You may specify tag instead of branch to build for specific tag
ARG BRANCH=master

LABEL Description="Fresh Yandex.Tank from github master branch with phantom" \
    Vendor="Yandex" \
    maintainer="direvius@yandex-team.ru" \
    YandexTank.version="${VERSION}" \
    Telegraf.version="${TELEGRAF_VERSION}"

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update -q && \
    apt-get install --no-install-recommends -yq \
        sudo     \
        vim      \
        wget     \
        curl     \
        less     \
        iproute2 \
        software-properties-common \
        telnet   \
        atop     \
        openssh-client \
        git            \
        python3-pip  && \
    add-apt-repository ppa:yandex-load/main -y && \
    apt-get update -q && \
    apt-get install -yq \
        phantom \
        phantom-ssl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/* /tmp/* /var/tmp/*

ENV TELEGRAF_VERSION=1.19.1-1
RUN curl -sL https://repos.influxdata.com/influxdb.key | gpg --import && \
    wget https://dl.influxdata.com/telegraf/releases/telegraf_${TELEGRAF_VERSION}_amd64.deb.asc && \
    wget https://dl.influxdata.com/telegraf/releases/telegraf_${TELEGRAF_VERSION}_amd64.deb && \
    gpg --batch --verify telegraf_${TELEGRAF_VERSION}_amd64.deb.asc telegraf_${TELEGRAF_VERSION}_amd64.deb && \
    dpkg -i telegraf_${TELEGRAF_VERSION}_amd64.deb && \
    rm -f telegraf_${TELEGRAF_VERSION}_amd64.deb*

ENV BUILD_DEPS="python3-dev build-essential gfortran libssl-dev libffi-dev"
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -yq --no-install-recommends ${BUILD_DEPS} && \
    pip3 install --upgrade setuptools && \
    pip3 install --upgrade pip==19.2.3 && \
    pip3 install https://api.github.com/repos/yandex/yandex-tank/tarball/${BRANCH} && \
    apt-get autoremove -y ${BUILD_DEPS} && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/* /tmp/* /var/tmp/* /root/.cache/*

COPY files/bashrc /root/.bashrc
COPY files/inputrc /root/.inputrc

VOLUME ["/var/loadtest"]
WORKDIR /var/loadtest
ENTRYPOINT ["/usr/local/bin/yandex-tank"]
