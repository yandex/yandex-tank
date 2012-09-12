#! /usr/bin/python
from Tank.ConsoleWorker import ConsoleTank
from optparse import OptionParser
import logging
import os
import sys
import traceback

if __name__ == "__main__":
    sys.path.append(os.path.dirname(__file__))
    parser = OptionParser()
    parser.add_option('-c', '--config', action='append', help="Path to INI file containing run options, multiple options accepted")
    # TODO: --non-interactive
    parser.add_option('-i', '--ignore-lock', action='store_true', dest='ignore_lock', help="Ignore lock files from concurrent instances")
    parser.add_option('-l', '--log', action='store', default="tank.log", help="Tank log file location")
    parser.add_option('-o', '--option', action='append', help="Set config option, multiple options accepted, example: -o 'shellexec.start=pwd'")
    parser.add_option('-q', '--quiet', action='store_true', help="Less console output, only errors and warnings")
    parser.add_option('-v', '--verbose', action='store_true', help="More console output, +debug messages")
    options, ammofile = parser.parse_args()

    # @type worker ConsoleTank
    worker=ConsoleTank(options, ammofile)
    worker.init_logging()
    try:     
        worker.configure()
        rc=worker.perform_test()
        exit(rc)
    except Exception, ex:
        logging.error("Exception: %s", ex)
        logging.debug("Exception: %s", traceback.format_exc(ex))
        exit(1)
        
    
                
