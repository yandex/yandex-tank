# Yandex.Tank
#
# VERSION 0.0.4

FROM ubuntu:focal

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
        gpg-agent      \
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
    pip3 install --upgrade pip && \
    pip3 install pyOpenSSL --upgrade && \
    pip3 install git+https://github.com/olgoncharov/yandex-tank.git && \
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
