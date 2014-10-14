#!/usr/bin/env python

import logging
import tornado.ioloop
import tornado.web
import os.path
import json
import uuid
from tornado import template
from pyjade.ext.tornado import patch_tornado
patch_tornado()

from tornadio2 import SocketConnection, TornadioRouter, SocketServer

from threading import Thread


class Client(SocketConnection):
    CONNECTION = None

    def on_open(self, info):
        print 'Client connected'
        Client.CONNECTION = self

    def on_message(self, msg):
        print 'Got', msg

    def on_close(self):
        print 'Client disconnected'
        Client.CONNECTION = None

class MainHandler(tornado.web.RequestHandler):
    cacher = None
    def initialize(self, template, reportUUID):
        self.template = template
        self.reportUUID = reportUUID

    def get(self):
        if MainHandler.cacher is not None:
            cached_data = {
              'data': MainHandler.cacher.get_all_data(),
              'uuid': self.reportUUID,
            }
        else:
            cached_data = {
              'data':{},
              'uuid': self.reportUUID,
            }
        self.render(self.template, cached_data=json.dumps(cached_data))

class ReportServer(object):
    def __init__(self, cacher):
        router = TornadioRouter(Client)
        self.reportUUID = uuid.uuid4().hex
        self.app = tornado.web.Application(
            router.apply_routes([
              (r"/", MainHandler, dict(template='index.jade', reportUUID=self.reportUUID)),
              (r"/brief\.html$", MainHandler, dict(template='brief.jade', reportUUID=self.reportUUID)),
              (r"/monitoring\.html$", MainHandler, dict(template='monitoring.jade', reportUUID=self.reportUUID)),
            ]),
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            debug=True,
            )
        MainHandler.cacher = cacher

    def serve(self):
        def run_server():
            SocketServer(self.app)
        th = Thread(target=run_server)
        th.start()

    def send(self, data):
        if Client.CONNECTION is not None:
            data['uuid'] = self.reportUUID
            Client.CONNECTION.send(json.dumps(data))


if __name__ == "__main__":
    main()
