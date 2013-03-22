#! /usr/bin/python
from Tank.ConsoleWorker import ConsoleTank
from optparse import OptionParser
import logging
import os
import sys
import traceback

class DevNullOpts:
    log = "/dev/null"

class CompletionHelperOptionParser(OptionParser):
    def __init__(self):
        OptionParser.__init__(self, add_help_option=False)
        self.add_option('--bash-switches-list', action='store_true', dest="list_switches", help="Options list")
        self.add_option('--bash-options-prev', action='store', dest="list_options_prev", help="Options list")
        self.add_option('--bash-options-cur', action='store', dest="list_options_cur", help="Options list")
    
    def error(self, msg):
        pass

    def exit(self, status=0, msg=None):
        pass

    def handle_request(self, parser):
        options = self.parse_args()[0]
        if options.list_switches:
            opts = []
            for option in parser.option_list:
                if not "--bash" in option.get_opt_string():
                    opts.append(option.get_opt_string())
            print ' '.join(opts)
            exit(0)
    
        if options.list_options_cur or options.list_options_prev:
            cmdtank = ConsoleTank(DevNullOpts(), None)
            cmdtank.core.load_configs(cmdtank.get_default_configs())
            cmdtank.core.load_plugins()
            
            opts = []
            for option in cmdtank.core.get_available_options():
                opts.append(cmdtank.core.SECTION + '.' + option + '=')
                
            for plugin in cmdtank.core.plugins.values():
                for option in plugin.get_available_options():
                    opts.append(plugin.SECTION + '.' + option + '=')
            print ' '.join(sorted(opts))
            exit(0)


if __name__ == "__main__":
    sys.path.append(os.path.dirname(__file__))
    parser = OptionParser()
    parser.add_option('-c', '--config', action='append', help="Path to INI file containing run options, multiple options accepted")
    parser.add_option('-i', '--ignore-lock', action='store_true', dest='ignore_lock', help="Ignore lock files from concurrent instances, has precedence before --lock-fail")
    parser.add_option('-f', '--fail-lock', action='store_true', dest='lock_fail', help="Don't wait for lock to release, fail test instead")
    parser.add_option('-l', '--log', action='store', default="tank.log", help="Tank log file location")
    parser.add_option('-m', '--manual-start', action='store_true', dest='manual_start', help="Wait for Enter key to start the test")
    parser.add_option('-n', '--no-rc', action='store_true', dest='no_rc', help="Don't load config files from /etc/yandex-tank and ~/.yandex-tank")
    parser.add_option('-o', '--option', action='append', help="Set config option, multiple options accepted, example: -o 'shellexec.start=pwd'")
    parser.add_option('-q', '--quiet', action='store_true', help="Less console output, only errors and warnings")
    parser.add_option('-s', '--scheduled-start', action='store', dest='scheduled_start', help="Start test at specified time, format 'YYYY-MM-DD hh:mm:ss', date part is optional")
    parser.add_option('-v', '--verbose', action='store_true', help="More console output, +debug messages")

    completion_helper = CompletionHelperOptionParser()
    completion_helper.handle_request(parser)
    
    
    options, ammofile = parser.parse_args()

    worker = ConsoleTank(options, ammofile)
    worker.init_logging()
    try:     
        worker.configure()
        rc = worker.perform_test()
        exit(rc)
    except Exception, ex:
        logging.error("Exception: %s", ex)
        logging.debug("Exception: %s", traceback.format_exc(ex))
        exit(1)
        
    
                
