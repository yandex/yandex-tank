FROM python:2.7
RUN mkdir -p /master-tank
WORKDIR /master-tank
ENV HOME /master-tank
ADD requirements.txt /master-tank
RUN apt-get update && \
    apt-get install -y vim
RUN pip install --upgrade setuptools
RUN pip install uwsgi
RUN pip install -r requirements.txt
ADD api.py api.yaml server.py uwsgi.ini /master-tank/
EXPOSE 80
CMD uwsgi --ini uwsgi.ini