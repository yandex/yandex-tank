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

# TODO: --manual-start
# TODO: add system resources busy check
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
        
        self.baseconfigs_location = '/etc/lunapark' 

        self.log_filename = self.options.log
        self.core.add_artifact_file(self.log_filename)
        self.log = logging.getLogger(__name__)

        self.signal_count = 0

    def set_baseconfigs_dir(self, directory):
        self.baseconfigs_location = directory
        
    def init_logging(self):
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)

        # create file handler which logs even debug messages
        if (self.log_filename):
            fh = logging.FileHandler(self.log_filename)
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s %(message)s"))
            logger.addHandler(fh)
            
        # create console handler with a higher log level
        ch = logging.StreamHandler(sys.stdout)
        
        if self.options.verbose:
            ch.setLevel(logging.DEBUG)
            ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s %(message)s"))
        elif self.options.quiet:
            ch.setLevel(logging.WARNING)
            ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s", "%H:%M:%S"))
        else:
            ch.setLevel(logging.INFO)
            ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s", "%H:%M:%S"))
        logger.addHandler(ch)



    def adapt_old_config(self, config):
        test_parser = ConfigParser.ConfigParser()
        try:
            test_parser.read(config)
            self.log.debug("Config passed ini format test: %s", config)
            return config
        except Exception, ex:
            self.log.warning("Config failed INI format test, consider upgrading it: %s", config)
            fd, corrected_file = tempfile.mkstemp(".conf", "corrected_")
            self.log.debug("Creating corrected INI config for it: %s", corrected_file)
            os.write(fd, "[" + self.MIGRATE_SECTION + "]\n")
            old_config = open(config, 'r').read()
            os.write(fd, old_config)
            return corrected_file

    def add_adapted_config(self, configs, conf_file):
        conf_file = self.adapt_old_config(conf_file)
        configs += [conf_file]
        self.core.add_artifact_file(conf_file, True)


    def override_config_from_cmdline(self):
        # override config options from command line
        if self.options.option: 
            for option_str in self.options.option:
                section = option_str[:option_str.index('.')]
                option = option_str[option_str.index('.') + 1:option_str.index('=')]
                value = option_str[option_str.index('=') + 1:]    
                self.log.debug("Override option: %s => [%s] %s=%s", option_str, section, option, value)
                self.core.set_option(section, option, value)
            
    
    def there_is_locks(self):
        # TODO: https://jira.yandex-team.ru/browse/LUNAPARK-1466
        rc = False
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
                        except Exception, e:
                            self.log.debug("Failed to delete lock %s: %s", full_name, e)
                    else:
                        rc = True        
                except Exception, e:
                    self.log.warn("Failed to load info from lock %s: %s", full_name, e)
                    rc = True        
        return rc
    
    
    def translate_old_options(self):
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
        if not self.options.ignore_lock:
            while self.there_is_locks():
                self.log.info("Waiting for 5s for retry...")
                time.sleep(5)
        else:
            self.log.warn("Lock files ignored. This is highly unrecommended practice!")        
        
        self.core.config.set_out_file(tempfile.mkstemp('.lock', 'lunapark_', self.LOCK_DIR)[1])
        
        configs = []

        try:
            for filename in os.listdir(self.baseconfigs_location):
                if fnmatch.fnmatch(filename, '*.conf'):
                    configs += [os.path.realpath(self.baseconfigs_location + os.sep + filename)]
        except OSError:
            self.log.warn(self.baseconfigs_location + ' is not acessible to get configs list')

        configs += [os.path.expanduser('~/.yandex-tank')]
        
        if not self.options.config:
            self.log.debug("No config passed via cmdline, using ./load.conf")
            conf_file = self.adapt_old_config(os.path.realpath('load.conf'))
            configs += [conf_file]
            self.core.add_artifact_file(conf_file, True)
        else:
            for config_file in self.options.config:
                self.add_adapted_config(configs, config_file)

        self.core.load_configs(configs)

        self.core.set_option(TankCore.SECTION, self.PID_OPTION, os.getpid())
        
        if self.ammofile:
            self.log.debug("Ammofile: %s", self.ammofile)
            self.core.set_option(self.MIGRATE_SECTION, 'ammofile', self.ammofile[0])

        self.translate_old_options()
        self.override_config_from_cmdline()
                    
        self.core.load_plugins()
        

    def graceful_shutdown(self):
        rc = 1
        self.log.info("Trying to shutdown gracefully...")
        rc = self.core.plugins_end_test(rc)
        rc = self.core.plugins_post_process(rc)
        self.log.info("Done graceful shutdown.")
        return rc
    
    
    def perform_test(self):
        self.log.info("Performing test")
        rc = 1
        try:
            self.core.plugins_configure()
            self.core.plugins_prepare_test()
            self.core.plugins_start_test()
            rc = self.core.wait_for_finish()
            rc = self.core.plugins_end_test(rc)
            rc = self.core.plugins_post_process(rc)
        
        except KeyboardInterrupt as ex:
            self.signal_count += 1
            self.log.debug("Caught KeyboardInterrupt: %s", traceback.format_exc(ex))
            try:
                rc = self.graceful_shutdown()
            except KeyboardInterrupt as ex:
                self.log.debug("Caught KeyboardInterrupt again: %s", traceback.format_exc(ex))
                self.log.info("User insists on exiting, aborting graceful shutdown...")
                rc = 1
                                
        except Exception as ex:
            self.log.debug("Exception: %s", traceback.format_exc(ex))
            sys.stdout.write(RealConsoleMarkup.RED)
            self.log.error("%s", ex)
            sys.stdout.write(RealConsoleMarkup.RESET)
            rc = self.graceful_shutdown()
        
        self.log.info("Done performing test with code %s", rc)
        return rc


