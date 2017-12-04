FROM python:2.7
RUN mkdir -p /tank-validator
WORKDIR /tank-validator
ENV HOME /tank-validator
ADD requirements.txt /tank-validator
RUN apt-get update && \
    apt-get install -y vim
RUN pip install --upgrade setuptools
RUN pip install uwsgi
RUN pip install git+https://github.com/fomars/yandex-tank.git@master#egg=yandextank
RUN pip install -r requirements.txt
ADD api.py api.yaml server.py uwsgi.ini /tank-validator/
EXPOSE 80
CMD uwsgi --ini uwsgi.ini