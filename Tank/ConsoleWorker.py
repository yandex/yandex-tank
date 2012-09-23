'''
Provides class to run TankCore from console environment
'''
from Tank.Core import TankCore
from Tank import Utils 
import ConfigParser
import fnmatch
import logging
import os
import sys
import tempfile
import time
import traceback
from Tank.Plugins.ConsoleOnline import RealConsoleMarkup

# TODO: 2 --manual-start
# TODO: 2 add system resources busy check
class ConsoleTank:
    """
    Worker class that runs tank core accepting cmdline params
    """

    MIGRATE_SECTION = 'migrate_old'

    PID_OPTION = 'pid'

    LOCK_DIR = '/var/lock'
    
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
        'inform': ('meta', ''),

        'autostop': ('autostop', ''),
        'monitoring_config': ('monitoring', 'config'),
        'manual_start': ('tank', ''),
        'http_base': ('meta', 'api_address')
    }
    
    
    def __init__(self, options, ammofile):
        # @type tank Tank.Core.TankCore
        self.core = TankCore()

        self.options = options
        self.ammofile = ammofile
        
        # TODO: 3 change it to /etc/yandex-tank
        self.baseconfigs_location = '/etc/lunapark' 

        self.log_filename = self.options.log
        self.core.add_artifact_file(self.log_filename)
        self.log = logging.getLogger(__name__)

        self.signal_count = 0

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
        opts = {}
        res = ''
        for line in old_lines:
            try:
                if line.strip() and line.strip()[0] == '#':
                    res+=line
                    continue
                option = line[:line.index('=')]
                value = line[line.index('=')+1:]
                if option not in opts.keys():
                    opts[option] = []
                opts[option].append(value.strip())
            except Exception:
                if option:
                    opts[option].append(line.strip())
                else:
                    res += line
    
        for option, values in opts.iteritems():
            res += option + '=' + "\n\t".join(values) + "\n"
    
        return res
    
    
    def __adapt_old_config(self, config):
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
            return corrected_file

    def __add_adapted_config(self, configs, conf_file):
        conf_file = self.__adapt_old_config(conf_file)
        configs += [conf_file]
        self.core.add_artifact_file(conf_file, True)


    def __override_config_from_cmdline(self):
        # override config options from command line
        if self.options.option: 
            for option_str in self.options.option:
                try:
                    section = option_str[:option_str.index('.')]
                    option = option_str[option_str.index('.') + 1:option_str.index('=')]
                except ValueError:
                    section = self.MIGRATE_SECTION
                    option = option_str[:option_str.index('=')]
                value = option_str[option_str.index('=') + 1:]    
                self.log.debug("Override option: %s => [%s] %s=%s", option_str, section, option, value)
                self.core.set_option(section, option, value)
            
    
    def __there_is_locks(self):
        retcode = False
        for filename in os.listdir(self.LOCK_DIR):
            if fnmatch.fnmatch(filename, 'lunapark_*.lock'):
                full_name = self.LOCK_DIR + os.sep + filename
                self.log.warn("Lock file present: %s", full_name)
                
                try:
                    info = ConfigParser.ConfigParser()
                    info.read(full_name)
                    pid = info.get(TankCore.SECTION, self.PID_OPTION)
                    if not Utils.pid_exists(int(pid)):
                        self.log.debug("Lock PID %s not exists, ignoring and trying to remove", pid)
                        try:
                            os.remove(full_name)
                        except Exception, exc:
                            self.log.debug("Failed to delete lock %s: %s", full_name, exc)
                    else:
                        retcode = True        
                except Exception, exc:
                    self.log.warn("Failed to load info from lock %s: %s", full_name, exc)
                    retcode = True        
        return retcode
    
    
    def __translate_old_options(self):
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
        if not self.options.ignore_lock:
            while self.__there_is_locks():
                if self.options.lock_fail:
                    raise RuntimeError("Lock file present, cannot continue")
                self.log.info("Waiting for 5s for retry...")
                time.sleep(5)
        else:
            self.log.warn("Lock files ignored. This is highly unrecommended practice!")        
        
        self.core.config.set_out_file(tempfile.mkstemp('.lock', 'lunapark_', self.LOCK_DIR)[1])
        
        configs = []

        try:
            for filename in os.listdir(self.baseconfigs_location):
                # TODO: 3 change extension to INI
                if fnmatch.fnmatch(filename, '*.conf'):
                    configs += [os.path.realpath(self.baseconfigs_location + os.sep + filename)]
        except OSError:
            self.log.warn(self.baseconfigs_location + ' is not acessible to get configs list')

        configs += [os.path.expanduser('~/.yandex-tank')]
        
        if not self.options.config:
            self.log.debug("No config passed via cmdline, using ./load.conf")
            conf_file = self.__adapt_old_config(os.path.realpath('load.conf'))
            configs += [conf_file]
            self.core.add_artifact_file(conf_file, True)
        else:
            for config_file in self.options.config:
                self.__add_adapted_config(configs, config_file)

        self.core.load_configs(configs)

        self.core.set_option(TankCore.SECTION, self.PID_OPTION, os.getpid())
        
        if self.ammofile:
            self.log.debug("Ammofile: %s", self.ammofile)
            self.core.set_option(self.MIGRATE_SECTION, 'ammofile', self.ammofile[0])

        self.__translate_old_options()
        self.__override_config_from_cmdline()
                    
        self.core.load_plugins()
        

    def __graceful_shutdown(self):
        retcode = 1
        self.log.info("Trying to shutdown gracefully...")
        retcode = self.core.plugins_end_test(retcode)
        retcode = self.core.plugins_post_process(retcode)
        self.log.info("Done graceful shutdown.")
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
            self.core.plugins_start_test()
            retcode = self.core.wait_for_finish()
            retcode = self.core.plugins_end_test(retcode)
            retcode = self.core.plugins_post_process(retcode)
        
        except KeyboardInterrupt as ex:
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
            retcode = self.__graceful_shutdown()
        
        self.log.info("Done performing test with code %s", retcode)
        return retcode


