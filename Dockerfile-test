FROM load/yandex-tank-pip:testing
WORKDIR /yandextank
RUN apt-get update && \
    apt-get install -y python3-pip
RUN pip3 install --upgrade setuptools
RUN pip3 install --upgrade pip
RUN pip3 install pytest
CMD pip3 install . && pytest -s
# docker run -v /path/to/yandextank:/yandextank --name my_container my_image
