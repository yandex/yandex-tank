# http://fragments.turtlemeat.com/pythonwebserver.php
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
import cgi
import ctypes
import inspect
import json
import logging
import os
import tempfile
import threading
import traceback
from urllib2 import HTTPError
import urlparse
import datetime

from Tank.API.client import TankAPIClient
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

            if isinstance(results[2], file):
                self.wfile.write(results[2].read())
            else:
                self.wfile.write()
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
                return self.__download_artifact(params)

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
            "tankcore": TankCore(),
            "exitcode": None
        }

    def __initiate_test(self, params):
        if 'exclusive' in params and int(params['exclusive']):
            exclusive = True
        else:
            exclusive = False

        if exclusive and self.live_tickets:
            raise HTTPError(None, 423, "Cannot obtain exclusive lock, the server is busy", {}, None)

        for ticket in self.live_tickets.values():
            if ticket['exclusive']:
                raise HTTPError(None, 423, "Cannot book the test, the server is exclusively booked", {}, None)

        ticket = self.__generate_new_ticket(exclusive)
        logging.debug("Created new ticket: %s", ticket)
        self.live_tickets[ticket[TankAPIClient.TICKET]] = ticket
        return self.__clean_ticket_objects(ticket)

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
        ticket_obj = self.__check_ticket(params)
        if ticket_obj['status'] != TankAPIClient.STATUS_BOOKED:
            ticket_dir = self.data_dir + os.path.sep + ticket_obj['ticket']
            ticket_obj['artifacts'] = os.listdir(ticket_dir)

        return self.__clean_ticket_objects(ticket_obj)

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

        ticket["worker"] = PrepareThread(ticket["tankcore"], load_ini)
        ticket["worker"].start()
        ticket['status'] = TankAPIClient.STATUS_PREPARING
        return 200, {}, {}

    def __test_start(self, params):
        ticket = self.__check_ticket(params)
        if ticket["status"] != TankAPIClient.STATUS_PREPARED:
            msg = "Ticket must be in %s status to start the test" % TankAPIClient.STATUS_PREPARED
            raise HTTPError(None, 422, msg, {}, None)

        ticket["worker"] = TestRunThread(ticket["tankcore"], self.data_dir + os.path.sep + ticket[TankAPIClient.TICKET])
        ticket["worker"].start()
        ticket["status"] = TankAPIClient.STATUS_RUNNING

    def __check_ticket(self, params):
        if not TankAPIClient.TICKET in params:
            raise HTTPError(None, 400, "Ticket parameter was not passed", {}, None)

        logging.debug("Live tickets: %s", self.live_tickets)
        ticket = params[TankAPIClient.TICKET]
        if ticket in self.live_tickets:
            ticket_obj = self.live_tickets[ticket]
            self.__refresh_ticket_status(ticket_obj)
            return ticket_obj
        else:
            ticket_dir = self.data_dir + os.path.sep + ticket
            if os.path.isdir(ticket_dir):
                with open(ticket_dir + os.path.sep + self.TICKET_INFO_JSON) as fd:
                    return json.loads(fd.read())

        raise HTTPError(None, 422, "Ticket not found", {}, None)

    def __refresh_ticket_status(self, ticket_obj):
        if ticket_obj['status'] == TankAPIClient.STATUS_PREPARING:
            if not ticket_obj['worker'].isAlive():
                if ticket_obj['worker'].retcode == 0:
                    ticket_obj['status'] = TankAPIClient.STATUS_PREPARED
                else:
                    ticket_obj['exitcode'] = ticket_obj['worker'].retcode
                    ticket_obj['status'] = TankAPIClient.STATUS_FINISHED
                    self.__move_ticket_to_offline(ticket_obj)

        if ticket_obj['status'] == TankAPIClient.STATUS_RUNNING:
            if not ticket_obj['worker'].isAlive():
                if ticket_obj['worker'].retcode == 0:
                    ticket_obj['status'] = TankAPIClient.STATUS_FINISHED
                else:
                    ticket_obj['exitcode'] = ticket_obj['worker'].retcode
                    ticket_obj['status'] = TankAPIClient.STATUS_FINISHED

    def __move_ticket_to_offline(self, ticket_obj):
        logging.info("Moving ticket to offline: %s", ticket_obj)
        ticket_dir = self.data_dir + os.path.sep + ticket_obj['ticket']
        with open(ticket_dir + os.path.sep + self.TICKET_INFO_JSON, 'w') as fd:
            json_str = json.dumps(self.__clean_ticket_objects(ticket_obj))
            logging.debug("Offline json: %s", json_str)
            fd.write(json_str)
        del self.live_tickets[ticket_obj['ticket']]

    def __clean_ticket_objects(self, base):
        ticket = {}
        for key in base:
            if key not in ('worker', "tankcore"):
                ticket[key] = base[key]

        return ticket

    def __download_artifact(self, params):
        ticket = self.__check_ticket(params)
        ticket_dir = self.data_dir + os.path.sep + ticket['ticket']
        filename = ticket_dir + os.path.sep + os.path.basename(params['filename'])
        logging.info("Sending file: %s", filename)
        fd = open(filename)
        return 200, {'Content-Type': 'application/octet-stream'}, fd


class InterruptibleThread(threading.Thread):
    def __async_raise(self, tid, exctype):
        """Raises an exception in the threads with id tid"""
        #http://stackoverflow.com/questions/323972/is-there-any-way-to-kill-a-thread-in-python
        if not inspect.isclass(exctype):
            raise TypeError("Only types can be raised (not instances)")
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid,
                                                         ctypes.py_object(exctype))
        if res == 0:
            raise ValueError("invalid thread id")
        elif res != 1:
            # "if it returns a number greater than one, you're in trouble,
            # and you should call it again with exc=NULL to revert the effect"
            ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, 0)
            raise SystemError("PyThreadState_SetAsyncExc failed")

    def __get_my_tid(self):
        """determines this (self's) thread id

        CAREFUL : this function is executed in the context of the caller
        thread, to get the identity of the thread represented by this
        instance.
        """
        if not self.isAlive():
            raise threading.ThreadError("the thread is not active")

        # do we have it cached?
        if hasattr(self, "_thread_id"):
            return self._thread_id

        # no, look for it in the _active dict
        for tid, tobj in threading._active.items():
            if tobj is self:
                self._thread_id = tid
                return tid

        raise AssertionError("could not determine the thread's id")

    def interrupt(self):
        logging.info("Interrupting the thread")
        self.__async_raise(self.__get_my_tid(), KeyboardInterrupt())


class AbstractTankThread(InterruptibleThread):
    def __init__(self, core, cwd):
        """

        :type core: tankcore.TankCore
        """
        super(AbstractTankThread, self).__init__()
        os.chdir(cwd)
        self.working_dir = cwd
        self.daemon = True
        self.core = core
        self.retcode = -1

    def graceful_shutdown(self):
        self.retcode = self.core.plugins_end_test(self.retcode)
        self.retcode = self.core.plugins_post_process(self.retcode)


class PrepareThread(AbstractTankThread):
    def __init__(self, core, config):
        """

        :type core: tankcore.TankCore
        """
        super(PrepareThread, self).__init__(core, os.path.dirname(config))
        self.config = config


    def run(self):
        logging.info("Preparing test")
        try:
            self.core.artifacts_base_dir = self.working_dir
            self.core.artifacts_dir = self.working_dir
            self.core.load_configs([self.config])
            self.core.load_plugins()
            self.core.plugins_configure()
            self.core.plugins_prepare_test()
            self.retcode = 0
        except Exception, exc:
            logging.info("Excepting during prepare: %s", traceback.format_exc(exc))
            self.retcode = 1
            self.graceful_shutdown()


class TestRunThread(AbstractTankThread):
    def run(self):
        logging.info("Starting test")
        try:
            self.core.plugins_start_test()
            self.retcode = self.core.wait_for_finish()
        except Exception, exc:
            logging.info("Excepting during test run: %s", traceback.format_exc(exc))
            self.retcode = 1
        finally:
            self.graceful_shutdown()

