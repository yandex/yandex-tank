#!/usr/bin/env python

import logging
import tornado.ioloop
import tornado.web
import os.path

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
    def get(self):
        self.render("index.jade")

class ReportServer(object):
    def __init__(self):
        router = TornadioRouter(Client)
        self.app = tornado.web.Application(
            router.apply_routes([(r"/", MainHandler)]),
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
        if Client.CONNECTION is not None:
            Client.CONNECTION.send(data)


if __name__ == "__main__":
    main()
