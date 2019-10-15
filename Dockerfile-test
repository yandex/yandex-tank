FROM load/yandex-tank-pip:testing
WORKDIR /yandextank
RUN apt-get update && \
    apt-get install -y python-pip
RUN pip install --upgrade setuptools
RUN pip install --upgrade pip
RUN pip install pytest
CMD pip install . && pytest -s
# docker run -v /path/to/yandextank:/yandextank --name my_container my_image