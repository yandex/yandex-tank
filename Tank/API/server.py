# http://fragments.turtlemeat.com/pythonwebserver.php
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
import json
import logging
import os
import tempfile
from urllib2 import HTTPError
import urlparse
import datetime

from Tank.API.client import TankAPIClient


class TankAPIServer(HTTPServer):
    """ web server starter """

    def __init__(self, server_address, handler_class, bind_and_activate=True):
        HTTPServer.allow_reuse_address = True
        HTTPServer.__init__(self, server_address, handler_class, bind_and_activate)
        self.handler = TankAPIHandler()


class HTTPAPIHandler(BaseHTTPRequestHandler):
    """ request proxy """

    def __init__(self, request, client_address, server):
        BaseHTTPRequestHandler.__init__(self, request, client_address, server)

    def do_GET(self):
        """ handle GET request """
        handler = self.server.handler
        try:
            results = handler.handle_get(self.path)
            self.send_response(results[0])
            for name, val in results[1].iteritems():
                self.send_header(name, val)
            self.end_headers()
            self.wfile.write(results[2])
        except HTTPError, exc:
            self.send_error(exc.getcode(), exc.msg)


class TankAPIHandler:
    def __init__(self):
        self.live_tickets = {}

    def handle_get(self, path):
        static = self.__handled_static(path)
        if static:
            return static
        else:
            parsed_path = urlparse.urlparse(path)
            params = urlparse.parse_qs(parsed_path.query)
            for k in params:
                params[k] = params[k][0]
            if parsed_path.path.endswith(".json"):
                return 200, {'Content-Type': 'application/json'}, json.dumps(
                    self.__handled_get_json(parsed_path.path, params))
            elif parsed_path.path == "/download_artifact":
                #TODO
                return 200, {'Content-Type': 'application/octet-stream'}, ''
            else:
                raise HTTPError(path, 404, "Not Found", {}, None)

    def __handled_static(self, path):
        if path == '/' or path == '/client.html':
            with open(os.path.dirname(__file__) + '/client.html') as fhandle:
                return 200, {'Content-Type': 'text/html'}, fhandle.read()
        if path == '/client.js':
            with open(os.path.dirname(__file__) + '/client.js') as fhandle:
                return 200, {'Content-Type': 'application/x-javascript'}, fhandle.read()
        elif path == "/favicon.ico":
            with open(os.path.dirname(__file__) + '/favicon.ico') as fhandle:
                return 200, {'Content-Type': 'image/x-icon'}, fhandle.read()
        else:
            return False

    def __handled_get_json(self, path, params):
        logging.debug("Get JSON: %s %s", path, params)
        if path == TankAPIClient.INITIATE_TEST_JSON:
            if 'exclusive' in params and params['exclusive']:
                exclusive = True
            else:
                exclusive = False

            if exclusive and self.live_tickets:
                raise HTTPError(path, 423, "Cannot obtain exclusive lock, the server is busy", {}, None)

            ticket = self.__generate_new_ticket(exclusive)
            logging.debug("Created new ticket: %s", ticket)
            self.live_tickets[ticket['ticket']] = ticket
            return ticket
        elif path == TankAPIClient.INTERRUPT_TEST_JSON:
            del self.live_tickets[params['ticket']]
            return {}

    def __generate_new_ticket(self, exclusive=False):
        ticket = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S.") + os.path.basename(tempfile.mktemp())
        return {"status": TankAPIClient.BOOKED, "ticket": ticket, "exclusive": exclusive}
