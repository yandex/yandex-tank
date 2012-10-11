from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from Tank.Plugins.Aggregator import AggregatorPlugin, AggregateResultListener
from tankcore import AbstractPlugin
from threading import Thread
import json
import logging
import os.path
import socket
import tankcore
import time

class WebOnlinePlugin(AbstractPlugin, Thread, AggregateResultListener):
    SECTION = "web"
    
    @staticmethod
    def get_key():
        return __file__
    
    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        Thread.__init__(self)
        self.daemon = True # Thread auto-shutdown
        self.port = 8080
        self.last_sec = None
        self.server = None
        self.interval = 60
        self.quantiles_data = []
        self.redirect = ''
    
    def configure(self):
        self.port = int(self.get_option("port", self.port))
        self.interval = int(tankcore.expand_to_seconds(self.get_option("interval", '1m')))
        self.redirect = self.get_option("redirect", self.redirect)
    
    def prepare_test(self):
        self.server = OnlineServer(('', self.port), WebOnlineHandler)
        self.server.owner = self
        aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        aggregator.add_result_listener(self)
    
    def start_test(self):
        self.start()
        
    def end_test(self, retcode):
        self.log.info("Shutting down local server")
        #self.server.shutdown() don't enable it since it leads to random deadlocks
        del self.server
        self.server = None
        return retcode
        
    def run(self):
        address = socket.gethostname()
        self.log.info("Starting local HTTP server for online view at port: http://%s:%s/", address, self.port)
        self.server.serve_forever()
    
    def aggregate_second(self, data):
        self.last_sec = data
        
        if not self.quantiles_data:
            header = ["timeStamp", "requestCount"]
            quantiles = [int(x) for x in sorted(data.overall.quantiles.keys(), reverse=True)]
            header += quantiles
            self.quantiles_data = [header, []]
            
        item_data = {"timeStamp":time.mktime(data.time.timetuple()), "requestCount":data.overall.planned_requests if data.overall.planned_requests else data.overall.RPS}
        for level, timing in data.overall.quantiles.iteritems():
            item_data[str(int(level))] = timing
        self.quantiles_data[1] += [item_data]
        
        while len(self.quantiles_data[1]) > self.interval:
            self.quantiles_data[1].pop(0)

    
#http://fragments.turtlemeat.com/pythonwebserver.php
class OnlineServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass, bind_and_activate=True):
        HTTPServer.__init__(self, server_address, RequestHandlerClass, bind_and_activate)
        self.last_sec = None
        self.owner = None
            
class WebOnlineHandler(BaseHTTPRequestHandler):
    def __init__(self, request, client_address, server):
        self.log = logging.getLogger(__name__)
        BaseHTTPRequestHandler.__init__(self, request, client_address, server)
    
    def log_error(self, fmt, *args):
        self.log.error(fmt % args)
    
    def log_message(self, fmt, *args):
        self.log.debug(fmt % args)
    
    def do_GET(self):
        try:
            if self.path == '/':
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                
                f = open(os.path.dirname(__file__) + '/online.html') 
                self.wfile.write(f.read())
                f.close()

                self.wfile.write('<!-- %s -->' % self.server.last_sec)
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
                elif self.path == '/redirect.json':
                    self.wfile.write('["' + self.server.owner.redirect + '"]')
            else:
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                
                f = open(os.path.dirname(__file__) + self.path) 
                self.wfile.write(f.read())
                f.close()
        except IOError:
            self.log.warning("404: %s" % self.path)
            self.send_error(404, 'File Not Found: %s' % self.path)


