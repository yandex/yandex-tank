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
from Tank.WebWorker import PrepareThread
from tankcore import TankCore


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
    TICKET_INFO_JSON = "ticket_info.json"

    def __init__(self):
        self.data_dir = "/tmp"
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
            TankAPIClient.TICKET: ticket,
            "status": TankAPIClient.STATUS_BOOKED,
            "exclusive": exclusive,
            "worker": None,
            "tankcore": None,
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
        self.live_tickets[ticket[TankAPIClient.TICKET]] = ticket
        return ticket

    def __interrupt_test(self, params):
        interruptible = (TankAPIClient.STATUS_PREPARING, TankAPIClient.STATUS_PREPARED, TankAPIClient.STATUS_RUNNING)
        ticket = self.__check_ticket(params)
        if ticket['status'] == TankAPIClient.STATUS_BOOKED:
            del self.live_tickets[params[TankAPIClient.TICKET]]
        elif ticket['status'] in interruptible:
            ticket['worker'].interrupt()
        elif ticket['status'] in (TankAPIClient.STATUS_FINISHING, TankAPIClient.STATUS_FINISHED):
            logging.info("No need to interrupt test in status: %s", ticket['status'])
        else:
            logging.warn("No live ticket to interrupt: %s", params[TankAPIClient.TICKET])
        return {}

    def __test_status(self, params):
        ticket = {}
        base = self.__check_ticket(params)
        for key in base:
            if key not in ('worker', "tankcore"):
                ticket[key] = base[key]

        return ticket

    def __prepare_test(self, params, headers, rfile):
        """

        :param headers: Message
        :param rfile:
        :return:
        """
        ticket = self.__check_ticket(params)
        if ticket['status'] != TankAPIClient.STATUS_BOOKED:
            msg = "Ticket must be in %s status to prepare the test" % TankAPIClient.STATUS_BOOKED
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

        ticket_dir = self.data_dir + os.path.sep + ticket[TankAPIClient.TICKET]
        logging.debug("Creating ticket dir: %s", ticket_dir)
        os.mkdir(ticket_dir)

        load_ini = None
        for field in form_data.keys():
            field_item = form_data[field]
            local_file = os.path.basename(field_item.filename)
            full_local_file = ticket_dir + os.path.sep + local_file
            logging.debug("Form data: %s => %s", field, full_local_file)

            if field == TankAPIClient.CONFIG:
                load_ini = full_local_file

            with open(full_local_file, "wb") as fd:
                fd.write(field_item.file.read())
                #files[] =

        if load_ini is None:
            raise RuntimeError('Error: config file is empty')

        ticket["tankcore"] = TankCore()
        ticket["worker"] = PrepareThread(ticket["tankcore"], load_ini)
        ticket["worker"].start()
        ticket['status'] = TankAPIClient.STATUS_PREPARING
        return 200, {}, {}

    def __test_start(self, params):
        ticket = self.__check_ticket(params)
        if ticket["status"] != TankAPIClient.STATUS_PREPARED:
            msg = "Ticket must be in %s status to start the test" % TankAPIClient.STATUS_PREPARED
            raise HTTPError(None, 422, msg, {}, None)
        ticket["status"] = TankAPIClient.STATUS_RUNNING

    def __check_ticket(self, params):
        if not TankAPIClient.TICKET in params:
            raise HTTPError(None, 400, "Ticket parameter was not passed", {}, None)

        logging.debug("Live tickets: %s", self.live_tickets)
        ticket = params[TankAPIClient.TICKET]
        if ticket in self.live_tickets:
            return self.live_tickets[ticket]
        else:
            ticket_dir = self.data_dir + os.path.sep + ticket
            if os.path.isdir(ticket_dir):
                with open(ticket_dir + os.path.sep + self.TICKET_INFO_JSON) as fd:
                    return json.loads(fd.read())

        raise HTTPError(None, 422, "Ticket not found", {}, None)
