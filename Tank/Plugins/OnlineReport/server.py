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

from tornadio2 import SocketConnection, TornadioRouter, SocketServer, event

from threading import Thread


class Client(SocketConnection):
    CONNECTIONS = set()

    def on_open(self, info):
        print 'Client connected'
        self.CONNECTIONS.add(self)

    def on_message(self, msg):
        print 'Got', msg

    def on_close(self):
        print 'Client disconnected'
        self.CONNECTIONS.remove(self)

    @event('heartbeat')
    def on_heartbeat(self):
        pass

class MainHandler(tornado.web.RequestHandler):
    def initialize(self, template, reportUUID, cacher):
        self.template = template
        self.reportUUID = reportUUID
        self.cacher = cacher

    def get(self):
        if self.cacher is not None:
            cached_data = {
              'data': self.cacher.get_all_data(),
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
              (r"/", MainHandler, dict(template='index.jade', reportUUID=self.reportUUID, cacher=cacher)),
              (r"/brief\.html$", MainHandler, dict(template='brief.jade', reportUUID=self.reportUUID, cacher=cacher)),
              (r"/monitoring\.html$", MainHandler, dict(template='monitoring.jade', reportUUID=self.reportUUID, cacher=cacher)),
            ]),
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            debug=True,
            )

    def serve(self):
        def run_server():
            SocketServer(self.app)
        th = Thread(target=run_server)
        th.start()

    def send(self, data):
        for connection in Client.CONNECTIONS:
            data['uuid'] = self.reportUUID
            connection.send(json.dumps(data))

    def reload(self):
        for connection in Client.CONNECTIONS:
            connection.emit('reload')
