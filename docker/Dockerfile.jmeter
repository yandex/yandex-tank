# Yandex.Tank with jmeter and some plugins

ARG VERSION=latest
FROM direvius/yandex-tank:"${VERSION}"
ARG VERSION
ARG JMETER_VERSION=3.3

MAINTAINER Alexey Lavrenuke <direvius@yandex-team.ru>

LABEL Description="Yandex.Tank with Apache jmeter" \
    Vendor="Yandex" \
    Jmeter.version="${JMETER_VERSION}"

ENV JVM="openjdk-8-jdk"

RUN DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -yq --no-install-recommends ${JVM} && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/* /tmp/* /var/tmp/*

ENV JMETER_PLUGINS="jpgc-csl,jpgc-tst,jpgc-dummy,jmeter-jdbc,jpgc-functions,jpgc-casutg,bzm-http2"
ENV JMETER_HOME=/usr/local/apache-jmeter-"${JMETER_VERSION}"
RUN wget https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-${JMETER_VERSION}.tgz --progress=dot:giga && \
    tar -xzf apache-jmeter-${JMETER_VERSION}.tgz -C /usr/local && \
    rm apache-jmeter-${JMETER_VERSION}.tgz

RUN cd ${JMETER_HOME}/lib/ && \
    for lib in \
        "kg/apc/cmdrunner/2.0/cmdrunner-2.0.jar" \
        "org/postgresql/postgresql/42.1.4/postgresql-42.1.4.jar"; \
    do local_name=$(echo "$lib" | awk -F'/' '{print $NF}') ; \
        wget "https://search.maven.org/remotecontent?filepath=${lib}" -O "${local_name}" --progress=dot:mega ;\
    done && \
    cd ${JMETER_HOME}/lib/ext && \
    wget 'https://search.maven.org/remotecontent?filepath=kg/apc/jmeter-plugins-manager/0.15/jmeter-plugins-manager-0.15.jar' -O jmeter-plugins-manager-0.15.jar --progress=dot:mega && \
    java -cp ${JMETER_HOME}/lib/ext/jmeter-plugins-manager-0.15.jar org.jmeterplugins.repository.PluginManagerCMDInstaller && \
    ${JMETER_HOME}/bin/PluginsManagerCMD.sh install "${JMETER_PLUGINS}" && \
    mkdir -p /etc/yandex-tank && \
    printf "jmeter:\n  jmeter_path: ${JMETER_HOME}/bin/jmeter\n  jmeter_ver: ${JMETER_VERSION}\n" > /etc/yandex-tank/10-jmeter.yaml
ENV PATH ${PATH}:${JMETER_HOME}/bin

COPY files/jmeter-large "${JMETER_HOME}"/bin/jmeter-large

