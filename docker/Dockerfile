# Yandex.Tank
#
# VERSION 0.0.4

FROM ubuntu:focal
MAINTAINER Yandex Load Team <load-public@yandex-team.ru>
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
        software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa -y && \
    add-apt-repository ppa:yandex-load/main -y && \
    apt-get update -q && \        
    apt-get install --no-install-recommends -yq \
        sudo     \
        vim      \
        wget     \
        curl     \
        less     \
        iproute2 \
        telnet   \
        atop     \
        openssh-client \
        git            \
        gpg-agent      \
        python3.12     \
        phantom        \
        phantom-ssl && \
    apt-get clean && \
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12 && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/* /tmp/* /var/tmp/*

ENV TELEGRAF_VERSION=1.29.1-1
# https://www.influxdata.com/time-series-platform/telegraf/
# influxdata-archive_compat.key GPG fingerprint:
#     9D53 9D90 D332 8DC7 D6C8 D3B9 D8FF 8E1F 7DF8 B07E
RUN wget -q https://repos.influxdata.com/influxdata-archive_compat.key
RUN echo '393e8779c89ac8d958f81f942f9ad7fb82a25e133faddaf92e15b16e6ac9ce4c influxdata-archive_compat.key' | sha256sum -c && cat influxdata-archive_compat.key | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/influxdata-archive_compat.gpg > /dev/null
RUN echo 'deb [signed-by=/etc/apt/trusted.gpg.d/influxdata-archive_compat.gpg] https://repos.influxdata.com/debian stable main' | sudo tee /etc/apt/sources.list.d/influxdata.list
RUN apt-get update 
RUN apt-get install telegraf

ENV BUILD_DEPS="python3.12-dev build-essential gfortran libssl-dev libffi-dev"
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -yq --no-install-recommends ${BUILD_DEPS} && \
    pip3 install --upgrade setuptools && \
    pip3 install --upgrade pip && \
    pip3 install https://api.github.com/repos/yandex/yandex-tank/tarball/${BRANCH} && \
    apt-get autoremove -y ${BUILD_DEPS} && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/* /tmp/* /var/tmp/* /root/.cache/*

RUN curl -L -v -o pandora https://github.com/yandex/pandora/releases/latest/download/pandora_0.3.8_linux_amd64 && \
    chmod +x ./pandora && \
    mv ./pandora /usr/local/bin/

COPY files/bashrc /root/.bashrc
COPY files/inputrc /root/.inputrc

VOLUME ["/var/loadtest"]
WORKDIR /var/loadtest
ENTRYPOINT ["/usr/local/bin/yandex-tank"]
