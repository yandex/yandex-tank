# http://fragments.turtlemeat.com/pythonwebserver.php
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
import json
import logging
import os


class TankAPIServer(HTTPServer):
    """ web server starter """

    def __init__(self, server_address, handler_class, bind_and_activate=True):
        HTTPServer.allow_reuse_address = True
        HTTPServer.__init__(self, server_address, handler_class, bind_and_activate)


class TankAPIHandler(BaseHTTPRequestHandler):
    """ request handler """

    def __init__(self, request, client_address, server):
        BaseHTTPRequestHandler.__init__(self, request, client_address, server)

    def do_GET(self):
        """ handle GET request """
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
                        data = (sec.overall.active_threads, sec.overall.planned_requests, sec.overall.rps,
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
            logging.warn("404: %s" % self.path)
            self.send_error(404, 'File Not Found: %s' % self.path)

