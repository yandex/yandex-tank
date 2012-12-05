'''
Provides class to run TankCore from console environment
'''
from Tank.Plugins.ConsoleOnline import RealConsoleMarkup
from tankcore import TankCore
import ConfigParser
import datetime
import fnmatch
import logging
import os
import sys
import tempfile
import time
import traceback
import signal

# required for non-tty python runs
def signal_handler(signal, frame):
    raise KeyboardInterrupt()
    
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# TODO: 2 add system resources busy check
class ConsoleTank:
    """
    Worker class that runs tank core accepting cmdline params
    """

    IGNORE_LOCKS = "ignore_locks"

    MIGRATE_SECTION = 'migrate_old'

    old_options_mapping = {
        'instances': ('phantom', ''),
        'tank_type': ('phantom', ''),
        'gatling_ip': ('phantom', ''),
        'ssl': ('phantom', ''),
        'address': ('phantom', ''),
        'port': ('phantom', ''),
        'writelog': ('phantom', ''),
        'phantom_http_line': ('phantom', ''),
        'phantom_http_field_num': ('phantom', ''),
        'phantom_http_field': ('phantom', ''),
        'phantom_http_entity': ('phantom', ''),

        'load': ('phantom', 'rps_schedule'),
        'instances_schedule': ('phantom', ''),
        'ammofile': ('phantom', ''),
        'loop': ('phantom', ''),
        'autocases': ('phantom', ''),
        'chosen_cases': ('phantom', ''),
        'uri': ('phantom', 'uris'),
        'header': ('phantom', 'headers'),
        
        'time_periods': ('aggregator', ''),
        'detailed_field': ('aggregator', ''),

        'task': ('meta', ''),
        'job_name': ('meta', ''),
        'job_dsc': ('meta', ''),
        'component': ('meta', ''),
        'regress': ('meta', ''),
        'ver': ('meta', ''),
        'inform': ('meta', 'notify'),

        'autostop': ('autostop', ''),
        'monitoring_config': ('monitoring', 'config'),
        'manual_start': ('tank', ''),
        'http_base': ('meta', 'api_address')
    }
    
    
    def __init__(self, options, ammofile):
        self.core = TankCore()

        self.options = options
        self.ammofile = ammofile
        
        self.baseconfigs_location = '/etc/yandex-tank' 

        self.log_filename = self.options.log
        self.core.add_artifact_file(self.log_filename)
        self.log = logging.getLogger(__name__)

        self.signal_count = 0
        self.scheduled_start = None

    def set_baseconfigs_dir(self, directory):
        '''
        Set directory where to read configs set
        '''
        self.baseconfigs_location = directory
        
    def init_logging(self):
        '''
        Set up logging, as it is very important for console tool
        '''
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)

        # create file handler which logs even debug messages
        if (self.log_filename):
            file_handler = logging.FileHandler(self.log_filename)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s %(message)s"))
            logger.addHandler(file_handler)
            
        # create console handler with a higher log level
        console_handler = logging.StreamHandler(sys.stdout)
        
        if self.options.verbose:
            console_handler.setLevel(logging.DEBUG)
            console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s %(message)s"))
        elif self.options.quiet:
            console_handler.setLevel(logging.WARNING)
            console_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s", "%H:%M:%S"))
        else:
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s", "%H:%M:%S"))
        logger.addHandler(console_handler)


    def __convert_old_multiline_options(self, old_lines):
        ''' supports old-school 'lunapark' tool configs ''' 
        opts = {}
        option = None
        res = ''
        for line in old_lines:
            try:
                if line.strip() and line.strip()[0] == '#':
                    res += line
                    continue
                option = line[:line.index('=')]
                value = line[line.index('=') + 1:]
                if option not in opts.keys():
                    opts[option] = []
                opts[option].append(value.strip())
            except Exception:
                if option:
                    opts[option].append(line.strip())
                else:
                    res += line.strip() + "\n"
    
        for option, values in opts.iteritems():
            res += option + '=' + "\n\t".join(values) + "\n"
    
        return res
    
    
    def __adapt_old_config(self, config):
        ''' supports old-school 'lunapark' tool configs ''' 
        test_parser = ConfigParser.ConfigParser()
        try:
            test_parser.read(config)
            self.log.debug("Config passed ini format test: %s", config)
            return config
        except Exception:
            self.log.warning("Config failed INI format test, consider upgrading it: %s", config)
            file_handle, corrected_file = tempfile.mkstemp(".ini", "corrected_")
            self.log.debug("Creating corrected INI config for it: %s", corrected_file)
            os.write(file_handle, "[" + self.MIGRATE_SECTION + "]\n")
            os.write(file_handle, self.__convert_old_multiline_options(open(config, 'r').readlines()))
            os.close(file_handle)
            return corrected_file

    def __add_adapted_config(self, configs, conf_file):
        ''' supports old-school 'lunapark' tool configs ''' 
        conf_file = self.__adapt_old_config(conf_file)
        configs += [conf_file]
        self.core.add_artifact_file(conf_file, True)


    def __override_config_from_cmdline(self):
        ''' override config options from command line'''
        if self.options.option: 
            self.core.apply_shorthand_options(self.options.option, self.MIGRATE_SECTION)            
    
    def __translate_old_options(self):
        ''' supports old-school 'lunapark' tool configs ''' 
        for old_option, value in self.core.config.get_options(self.MIGRATE_SECTION):
            if old_option in self.old_options_mapping.keys():
                new_sect = self.old_options_mapping[old_option][0]
                new_opt = self.old_options_mapping[old_option][1] if self.old_options_mapping[old_option][1] else old_option
                self.log.debug("Translating old option %s=%s into new: %s.%s", old_option, value, new_sect, new_opt)
                self.core.set_option(new_sect, new_opt, value)
            else:
                self.log.warn("Unknown old option, please add it to translation mapping: %s=%s", old_option, value)

        if self.core.config.config.has_section(self.MIGRATE_SECTION):                
            self.core.config.config.remove_section(self.MIGRATE_SECTION)

                
    def configure(self):
        '''
        Make all console-specific preparations before running Tank
        '''
        if self.options.ignore_lock:
            self.log.warn("Lock files ignored. This is highly unrecommended practice!")
        
        while True:        
            try:
                self.core.get_lock(self.options.ignore_lock)
                break
            except Exception:
                if self.options.lock_fail:
                    raise RuntimeError("Lock file present, cannot continue")
                self.log.info("Waiting 5s for retry...")
                time.sleep(5)
        
        try:
            configs = []
            
            if not self.options.no_rc:
                try:
                    conf_files = os.listdir(self.baseconfigs_location)
                    conf_files.sort()
                    for filename in conf_files:
                        if fnmatch.fnmatch(filename, '*.ini'):
                            configs += [os.path.realpath(self.baseconfigs_location + os.sep + filename)]
                except OSError:
                    self.log.warn(self.baseconfigs_location + ' is not acessible to get configs list')
        
                configs += [os.path.expanduser('~/.yandex-tank')]
            
            if not self.options.config:
                if os.path.exists(os.path.realpath('load.ini')):
                    self.log.info("No config passed via cmdline, using ./load.ini")
                    configs += [os.path.realpath('load.ini')]
                    self.core.add_artifact_file(os.path.realpath('load.ini'), True)
                elif os.path.exists(os.path.realpath('load.conf')):
                    # just for old 'lunapark' compatibility
                    self.log.warn("Using 'load.conf' is unrecommended, please use 'load.ini' instead")
                    conf_file = self.__adapt_old_config(os.path.realpath('load.conf'))
                    configs += [conf_file]
                    self.core.add_artifact_file(conf_file, True)
            else:
                for config_file in self.options.config:
                    self.__add_adapted_config(configs, config_file)
    
            self.core.load_configs(configs)
    
            if self.ammofile:
                self.log.debug("Ammofile: %s", self.ammofile)
                self.core.set_option(self.MIGRATE_SECTION, 'ammofile', self.ammofile[0])
    
            self.__translate_old_options()
            self.__override_config_from_cmdline()
                        
            self.core.load_plugins()
            
            if self.options.scheduled_start:
                try:
                    self.scheduled_start = datetime.datetime.strptime(self.options.scheduled_start, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    self.scheduled_start = datetime.datetime.strptime(datetime.datetime.now().strftime('%Y-%m-%d ') + self.options.scheduled_start, '%Y-%m-%d %H:%M:%S')

            if self.options.ignore_lock:
                self.core.set_option(self.core.SECTION, self.IGNORE_LOCKS, "1")
                
        except Exception, ex:
            self.log.info("Exception: %s", traceback.format_exc(ex))
            sys.stdout.write(RealConsoleMarkup.RED)
            self.log.error("%s", ex)
            sys.stdout.write(RealConsoleMarkup.RESET)
            sys.stdout.write(RealConsoleMarkup.TOTAL_RESET)
            self.core.release_lock()
            raise ex

    def __graceful_shutdown(self):
        ''' call shutdown routines '''
        retcode = 1
        self.log.info("Trying to shutdown gracefully...")
        retcode = self.core.plugins_end_test(retcode)
        retcode = self.core.plugins_post_process(retcode)
        self.log.info("Done graceful shutdown")
        return retcode
    
    
    def perform_test(self):
        '''
        Run the test sequence via Tank Core
        '''
        self.log.info("Performing test")
        retcode = 1
        try:
            self.core.plugins_configure()
            self.core.plugins_prepare_test()
            if self.scheduled_start:
                self.log.info("Waiting scheduled time: %s...", self.scheduled_start)
                while datetime.datetime.now() < self.scheduled_start:
                    self.log.debug("Not yet: %s < %s", datetime.datetime.now(), self.scheduled_start)
                    time.sleep(1)
                self.log.info("Time has come: %s", datetime.datetime.now())
            
            if self.options.manual_start:
                raw_input("Press Enter key to start test:")
            
            self.core.plugins_start_test()
            retcode = self.core.wait_for_finish()
            retcode = self.core.plugins_end_test(retcode)
            retcode = self.core.plugins_post_process(retcode)
        
        except KeyboardInterrupt as ex:
            sys.stdout.write(RealConsoleMarkup.YELLOW)
            self.log.info("Do not press Ctrl+C again, the test will be broken otherwise")
            sys.stdout.write(RealConsoleMarkup.RESET)
            sys.stdout.write(RealConsoleMarkup.TOTAL_RESET)
            self.signal_count += 1
            self.log.debug("Caught KeyboardInterrupt: %s", traceback.format_exc(ex))
            try:
                retcode = self.__graceful_shutdown()
            except KeyboardInterrupt as ex:
                self.log.debug("Caught KeyboardInterrupt again: %s", traceback.format_exc(ex))
                self.log.info("User insists on exiting, aborting graceful shutdown...")
                retcode = 1
                                
        except Exception as ex:
            self.log.info("Exception: %s", traceback.format_exc(ex))
            sys.stdout.write(RealConsoleMarkup.RED)
            self.log.error("%s", ex)
            sys.stdout.write(RealConsoleMarkup.RESET)
            sys.stdout.write(RealConsoleMarkup.TOTAL_RESET)
            retcode = self.__graceful_shutdown()
            self.core.release_lock()
        
        self.log.info("Done performing test with code %s", retcode)
        return retcode


