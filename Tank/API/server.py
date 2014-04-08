# http://fragments.turtlemeat.com/pythonwebserver.php
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
import cgi
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
        try:
            results = self.server.handler.handle_get(self.path)
            self.send_response(results[0])
            for name, val in results[1].iteritems():
                self.send_header(name, val)
            self.end_headers()
            self.wfile.write(results[2])
        except HTTPError, exc:
            logging.info("HTTP Error Response: %s", exc)
            self.send_error(exc.getcode(), exc.msg)

    def do_POST(self):
        try:
            results = self.server.handler.handle_post(self.path, self.headers, self.rfile)
            logging.debug("POST result: %s", results)
            self.send_response(results[0])
            for name, val in results[1].iteritems():
                self.send_header(name, val)
            self.end_headers()
            self.wfile.write(results[2])
        except HTTPError, exc:
            logging.info("HTTP Error Response: %s", exc)
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

    def handle_post(self, path, headers, rfile):
        parsed_path = urlparse.urlparse(path)
        params = urlparse.parse_qs(parsed_path.query)

        for k in params:
            params[k] = params[k][0]

        if parsed_path.path.endswith(".json"):
            logging.debug("Post JSON: %s %s\n%s", parsed_path.path, params, rfile)
            if parsed_path.path == TankAPIClient.PREPARE_TEST_JSON:
                return self.__prepare_test(params, headers, rfile)

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
            return self.__initiate_test(params)
        elif path == TankAPIClient.INTERRUPT_TEST_JSON:
            return self.__interrupt_test(params)
        elif path == TankAPIClient.TEST_STATUS_JSON:
            return self.__test_status(params)
        elif path == TankAPIClient.START_TEST_JSON:
            return self.__test_start(params)
        else:
            raise HTTPError(path, 404, "Not Found", {}, None)

    def __generate_new_ticket(self, exclusive=False):
        ticket = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S.") + os.path.basename(tempfile.mktemp())
        return {
            "ticket": ticket,
            "status": TankAPIClient.BOOKED,
            "exclusive": exclusive,
            "worker": None
        }

    def __initiate_test(self, params):
        if 'exclusive' in params and int(params['exclusive']):
            exclusive = True
        else:
            exclusive = False

        if exclusive and self.live_tickets:
            raise HTTPError(None, 423, "Cannot obtain exclusive lock, the server is busy", {}, None)

        ticket = self.__generate_new_ticket(exclusive)
        logging.debug("Created new ticket: %s", ticket)
        self.live_tickets[ticket['ticket']] = ticket
        return ticket

    def __interrupt_test(self, params):
        if params['ticket'] in self.live_tickets:
            # TODO: need to initiate worker shutdown
            del self.live_tickets[params['ticket']]
        else:
            logging.warn("No live ticket to interrupt: %s", params['ticket'])
        return {}

    def __test_status(self, params):
        return self.__check_live_ticket(params)

    def __test_start(self, params):
        pass

    def __prepare_test(self, params, headers, rfile):
        """

        :param headers: Message
        :param rfile:
        :return:
        """
        ticket = self.__check_live_ticket(params)
        if ticket['status'] != TankAPIClient.BOOKED:
            msg = "Ticket must be in %s status to prepare the test" % TankAPIClient.BOOKED
            raise HTTPError(None, 422, msg, {}, None)

        logging.debug('Headers: %s' % headers)

        ctype_header = headers.getheader('content-type')
        if not ctype_header:
            raise HTTPError(None, 400, "Missing Content-Type header", {}, None)

        ctype, pdict = cgi.parse_header(ctype_header)
        logging.debug('ctype %s, pdict %s' % (ctype, pdict))
        if not ctype == 'multipart/form-data':
            raise Exception('Incorrect content_type %s.' % ctype)

        form_data = cgi.FieldStorage(fp=rfile, headers=headers,
                                     environ={'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': headers['Content-Type'], })
        load_ini = None
        for field in form_data.keys():
            field_item = form_data[field]
            logging.debug("Form data: %s => %s", field, field_item.filename)
            if field == TankAPIClient.CONFIG:
                load_ini = field_item.file.read()
                local_file = "load.ini"
            else:
                local_file = os.path.basename(field_item.filename)

            with open(local_file, "wb") as fd:
                fd.write(field_item.file.read())
                #files[] =

        if load_ini is None:
            raise RuntimeError('Error: config file is empty')

        return 200, {}, {}

    def __check_live_ticket(self, params):
        if not "ticket" in params:
            raise HTTPError(None, 400, "Ticket parameter was not passed", {}, None)

        logging.debug("Live tickets: %s", self.live_tickets)
        if not params['ticket'] in self.live_tickets:
            raise HTTPError(None, 422, "Ticket not found", {}, None)

        return self.live_tickets[params['ticket']]
