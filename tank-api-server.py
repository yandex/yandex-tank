#! /usr/bin/env python
import fnmatch
import logging
from optparse import OptionParser
import os
import socket
import sys

from Tank.API.client import TankAPIClient
from Tank.API.server import TankAPIServer, HTTPAPIHandler
from tankcore import TankCore


SECTION = "server"


def get_configs():
    """
    copied this from ConsoleWorker, had no better idea
    """
    configs = []
    dirname = "/etc/yandex-tank"
    conf_files = os.listdir(dirname)
    conf_files.sort()
    for filename in conf_files:
        if fnmatch.fnmatch(filename, '*.ini'):
            configs += [os.path.realpath(dirname + os.sep + filename)]
    return configs


def init_logging(level, log_filename=None):
    """        Set up logging, as it is very important for console tool        """
    logger = logging.getLogger()
    logger.setLevel(level)

    # create file handler which logs even debug messages
    if log_filename:
        file_handler = logging.FileHandler(log_filename)
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s %(message)s"))
        logger.addHandler(file_handler)

    # create console handler with a higher log level
    stderr_hdl = logging.StreamHandler(sys.stderr)
    fmt_verbose = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s %(message)s")
    stderr_hdl.setFormatter(fmt_verbose)
    logger.addHandler(stderr_hdl)


if __name__ == "__main__":
    sys.path.append(os.path.realpath(os.path.dirname(__file__)))
    parser = OptionParser()
    parser.add_option('-c', '--config', action='append',
                      help="Path to INI file containing run options, multiple options accepted")
    parser.add_option('-l', '--log', action='store', default="tank-server.log", help="Tank log file location")
    parser.add_option('-d', '--debug', action='store_true', help="Enable debug messages")
    options, _ = parser.parse_args()

    init_logging(logging.DEBUG if options.debug else logging.INFO, options.log)

    ini_reader = TankCore()
    if options.config:
        ini_reader.load_configs(options.config)
    else:
        ini_reader.load_configs(get_configs())

    address = socket.gethostname()
    port = int(ini_reader.get_option(SECTION, "port", TankAPIClient.DEFAULT_PORT))
    server = TankAPIServer(('', port), HTTPAPIHandler)
    logging.info("Starting HTTP server: http://%s:%s/", address, port)
    server.serve_forever()