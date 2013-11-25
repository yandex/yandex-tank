''' local webserver with online graphs '''
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
import json
import logging
import os.path
import socket
import time

from Tank.Plugins.Aggregator import AggregatorPlugin, AggregateResultListener
from tankcore import AbstractPlugin
import tankcore


class WebOnlinePlugin(AbstractPlugin, Thread, AggregateResultListener):
    ''' web online plugin '''
    SECTION = "web"

    @staticmethod
    def get_key():
        return __file__

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        Thread.__init__(self)
        self.daemon = True  # Thread auto-shutdown
        self.port = 8080
        self.last_sec = None
        self.server = None
        self.interval = 60
        self.quantiles_data = []
        self.codes_data = []
        self.avg_data = []
        self.redirect = ''
        self.manual_stop = 0

    def get_available_options(self):
        return ["port", "interval", "redirect", "manual_stop"]

    def configure(self):
        self.port = int(self.get_option("port", self.port))
        self.interval = int(tankcore.expand_to_seconds(self.get_option("interval", '1m')))
        self.redirect = self.get_option("redirect", self.redirect)
        self.manual_stop = int(self.get_option('manual_stop', self.manual_stop))


    def prepare_test(self):
        try:
            self.server = OnlineServer(('', self.port), WebOnlineHandler)
            self.server.owner = self
            aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
            aggregator.add_result_listener(self)
        except Exception, ex:
            self.log.warning("Failed to start web results server: %s", ex)


    def start_test(self):
        self.start()


    def end_test(self, retcode):
        # self.log.info("Shutting down local server")
        # self.server.shutdown() don't enable it since it leads to random deadlocks
        if self.manual_stop:
            raw_input('Press Enter, to close webserver.')

        if self.redirect:
            time.sleep(2)

        del self.server
        self.server = None
        return retcode


    def run(self):
        if (self.server):
            address = socket.gethostname()
            self.log.info("Starting local HTTP server for online view at port: http://%s:%s/", address, self.port)
            self.server.serve_forever()


    def __calculate_quantiles(self, data):
        ''' prepare response quantiles data '''
        if not self.quantiles_data:
            header = ["timeStamp", "requestCount"]
            quantiles = [int(x) for x in sorted(data.overall.quantiles.keys(), reverse=True)]
            header += quantiles
            self.quantiles_data = [header, []]
        item_data = {"timeStamp": time.mktime(data.time.timetuple()),
                     "requestCount": data.overall.planned_requests if data.overall.planned_requests else data.overall.RPS}
        for level, timing in data.overall.quantiles.iteritems():
            item_data[str(int(level))] = timing

        self.quantiles_data[1] += [item_data]
        while len(self.quantiles_data[1]) > self.interval:
            self.quantiles_data[1].pop(0)


    def __calculate_avg(self, data):
        ''' prepare response avg times data '''
        if not self.avg_data:
            header = ["timeStamp", "connect", "send", "latency", "receive"]
            self.avg_data = [header, []]
        item_data = {
            "timeStamp": time.mktime(data.time.timetuple()),
            'connect': data.overall.avg_connect_time,
            'send': data.overall.avg_send_time, 'latency': data.overall.avg_latency,
            'receive': data.overall.avg_receive_time
        }

        self.avg_data[1] += [item_data]
        while len(self.avg_data[1]) > self.interval:
            self.avg_data[1].pop(0)


    def __calculate_codes(self, data):
        ''' prepare response codes data '''
        if not self.codes_data:
            header = ["timeStamp", "net", "2xx", "3xx", "4xx", "5xx", "Non-HTTP"]
            self.codes_data = [header, []]

        item_data = {"timeStamp": time.mktime(data.time.timetuple()), "net": 0, "2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0,
                     "Non-HTTP": 0}

        net = 0
        for code, count in data.overall.net_codes.iteritems():
            if code != "0":
                net += count
        item_data['net'] = net

        for code, count in data.overall.http_codes.iteritems():
            if code[0] == '2':
                item_data['2xx'] += count
            elif code[0] == '3':
                item_data['3xx'] += count
            elif code[0] == '4':
                item_data['4xx'] += count
            elif code[0] == '5':
                item_data['5xx'] += count
            else:
                item_data['Non-HTTP'] += count

        self.codes_data[1] += [item_data]
        while len(self.codes_data[1]) > self.interval:
            self.codes_data[1].pop(0)


    def aggregate_second(self, data):
        self.last_sec = data

        self.__calculate_quantiles(data)
        self.__calculate_avg(data)
        self.__calculate_codes(data)


# http://fragments.turtlemeat.com/pythonwebserver.php
class OnlineServer(HTTPServer):
    ''' web server starter '''

    def __init__(self, server_address, handler_class, bind_and_activate=True):
        HTTPServer.allow_reuse_address = True
        HTTPServer.__init__(self, server_address, handler_class, bind_and_activate)
        self.owner = None


class WebOnlineHandler(BaseHTTPRequestHandler):
    ''' request handler '''

    def __init__(self, request, client_address, server):
        self.log = logging.getLogger(__name__)
        BaseHTTPRequestHandler.__init__(self, request, client_address, server)

    def log_error(self, fmt, *args):
        self.log.error(fmt % args)

    def log_message(self, fmt, *args):
        self.log.debug(fmt % args)

    def do_GET(self):
        ''' handle GET request '''
        try:
            if self.path == '/':
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()

                fhandle = open(os.path.dirname(__file__) + '/online.html')
                self.wfile.write(fhandle.read())
                fhandle.close()

            elif self.path.endswith(".ico"):
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write("")
            elif self.path.endswith(".json"):
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                if self.path == '/Q.json':
                    self.wfile.write(json.dumps(self.server.owner.quantiles_data))
                if self.path == '/HTTP.json':
                    self.wfile.write(json.dumps(self.server.owner.codes_data))
                if self.path == '/Avg.json':
                    self.wfile.write(json.dumps(self.server.owner.avg_data))
                elif self.path == '/redirect.json':
                    self.wfile.write('["%s"]' % self.server.owner.redirect)
                elif self.path == '/numbers.json':
                    sec = self.server.owner.last_sec
                    net = 0
                    if sec:
                        for code, count in sec.overall.net_codes.iteritems():
                            if code != "0":
                                net += count
                        data = (sec.overall.active_threads, sec.overall.planned_requests, sec.overall.RPS,
                                sec.overall.avg_response_time, net)
                    else:
                        data = (0, 0, 0, 0, 0)
                    self.wfile.write('{"instances": %s, "planned": %s, "actual": %s, "avg": %s, "net": %s}' % data)
            else:
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()

                fhandle = open(os.path.dirname(__file__) + self.path)
                self.wfile.write(fhandle.read())
                fhandle.close()
        except IOError:
            self.log.warning("404: %s" % self.path)
            self.send_error(404, 'File Not Found: %s' % self.path)


