# Android performance testing environment with yandex-tank.
# version 0.0.1

FROM direvius/yandex-tank

MAINTAINER Alexey Lavrenuke <direvius@gmail.com>

ENV DEBIAN_FRONTEND noninteractive

RUN add-apt-repository ppa:webupd8team/java && apt update && \
    echo "oracle-java8-installer shared/accepted-oracle-license-v1-1 select true" | debconf-set-selections && \
    apt -y install oracle-java8-installer

RUN wget https://dl.google.com/android/android-sdk_r24.4.1-linux.tgz && \
    tar -xvzf android-sdk_r24.4.1-linux.tgz && \
    mv android-sdk-linux /usr/local/android-sdk


ENV ANDROID_HOME /usr/local/android-sdk
ENV PATH $PATH:$ANDROID_HOME/tools
ENV PATH $PATH:$ANDROID_HOME/platform-tools
ENV JAVA_HOME /usr/lib/jvm/java-8-oracle


ARG MAVEN_VERSION=3.3.9
ARG USER_HOME_DIR="/root"

RUN mkdir -p /usr/share/maven /usr/share/maven/ref \
  && curl -fsSL http://apache.osuosl.org/maven/maven-3/$MAVEN_VERSION/binaries/apache-maven-$MAVEN_VERSION-bin.tar.gz \
    | tar -xzC /usr/share/maven --strip-components=1 \
  && ln -s /usr/share/maven/bin/mvn /usr/bin/mvn

ENV MAVEN_HOME /usr/share/maven
ENV MAVEN_CONFIG "$USER_HOME_DIR/.m2"

VOLUME "$USER_HOME_DIR/.m2"

# some street magic
RUN echo "y" | android update sdk --no-ui --force --filter platform-tools

RUN pip3 install uiautomator Appium-Python-Client

RUN curl -sL https://deb.nodesource.com/setup_6.x | bash - && \
    apt install -y nodejs && npm install -g appium
