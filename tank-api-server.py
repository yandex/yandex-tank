#! /usr/bin/env python
import logging
from optparse import OptionParser
import socket

from Tank.API.server import TankAPIServer, TankAPIHandler


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option('-c', '--config', action='store', help="Path to INI file containing run options")

    address = socket.gethostname()
    port = 8080
    server = TankAPIServer(('', port), TankAPIHandler)
    logging.info("Starting local HTTP server for online view at port: http://%s:%s/", address, port)
    server.serve_forever()