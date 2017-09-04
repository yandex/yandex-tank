""" Provides classes to run TankCore from console environment """
from ConfigParser import ConfigParser, MissingSectionHeaderError, NoOptionError
import datetime
import fnmatch
import glob
import logging
import os
import sys
import tempfile
import time
import traceback
import signal
from optparse import OptionParser

import yaml
from pkg_resources import resource_filename
from ..config_converter.converter import convert_ini, convert_single_option
from .tankcore import TankCore, LockError
from ..common.resource import manager as resource_manager


DEFAULT_CONFIG = 'load.yaml'


class RealConsoleMarkup(object):
    '''
    Took colors from here: https://www.siafoo.net/snippet/88
    '''
    WHITE_ON_BLACK = '\033[37;40m'
    TOTAL_RESET = '\033[0m'
    clear = "\x1b[2J\x1b[H"
    new_line = u"\n"

    YELLOW = '\033[1;33m'
    RED = '\033[1;31m'
    RED_DARK = '\033[31;3m'
    RESET = '\033[1;m'
    CYAN = "\033[1;36m"
    GREEN = "\033[1;32m"
    WHITE = "\033[1;37m"
    MAGENTA = '\033[1;35m'
    BG_MAGENTA = '\033[1;45m'
    BG_GREEN = '\033[1;42m'
    BG_BROWN = '\033[1;43m'
    BG_CYAN = '\033[1;46m'

    def clean_markup(self, orig_str):
        ''' clean markup from string '''
        for val in [
            self.YELLOW, self.RED, self.RESET, self.CYAN, self.BG_MAGENTA,
            self.WHITE, self.BG_GREEN, self.GREEN, self.BG_BROWN,
            self.RED_DARK, self.MAGENTA, self.BG_CYAN
        ]:
            orig_str = orig_str.replace(val, '')
        return orig_str


class SingleLevelFilter(logging.Filter):
    """Exclude or approve one msg type at a time.    """

    def __init__(self, passlevel, reject):
        logging.Filter.__init__(self)
        self.passlevel = passlevel
        self.reject = reject

    def filter(self, record):
        if self.reject:
            return record.levelno != self.passlevel
        else:
            return record.levelno == self.passlevel


def signal_handler(sig, frame):
    """ required for non-tty python runs to interrupt """
    raise KeyboardInterrupt()


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def load_cfg(cfg_filename):
    """

    :type cfg_filename: str
    """
    if cfg_filename.endswith('.yaml'):
        with open(cfg_filename) as f:
            cfg = yaml.load(f)
    else:
        cfg = convert_ini(cfg_filename)
    return cfg


def cfg_folder_loader(path):
    """
    :type path: str
    """
    CFG_WILDCARD = '*.yaml'
    return [load_cfg(filename) for filename in sorted(glob.glob(os.path.join(path, CFG_WILDCARD)))]


def load_core_base_cfg():
    return load_cfg(resource_filename(__name__, 'config/00-base.yaml'))


def load_local_base_cfgs():
    return cfg_folder_loader('/etc/yandex-tank')


def parse_options(options):
    """
    :type options: list of str
    :rtype: list of dict
    """
    if options is None:
        return []
    else:
        return [
            convert_single_option(key.strip(), value.strip())
            for key, value
            in [option.split('=') for option in options]
        ]


def apply_shorthand_options(config, options, default_section='DEFAULT'):
    """

    :type config: ConfigParser
    """
    if not options:
        return config
    for option_str in options:
        key, value = option_str.split('=')
        try:
            section, option = key.split('.')
        except ValueError:
            section = default_section
            option = key
        if not config.has_section(section):
            config.add_section(section)
        config.set(section, option, value)
    return config


def load_ini_cfgs(config_files):
    config_filenames = [resource_manager.resource_filename(config) for config in config_files]
    cfg = ConfigParser()
    cfg.read(config_filenames)

    dotted_options = []
    if cfg.has_section('tank'):
        for option, value in cfg.items('tank'):
            if '.' in option:
                dotted_options += [option + '=' + value]
    else:
        cfg.add_section('tank')
    cfg = apply_shorthand_options(cfg, dotted_options)
    cfg.set('tank', 'pid', str(os.getpid()))
    return cfg


def get_default_configs():
    """ returns default configs list, from /etc and home dir """
    # initialize basic defaults
    configs = [resource_filename(__name__, 'config/00-base.ini')]
    baseconfigs_location = '/etc/yandex-tank'
    try:
        conf_files = sorted(os.listdir(baseconfigs_location))
        for filename in conf_files:
            if fnmatch.fnmatch(filename, '*.ini'):
                configs += [
                    os.path.realpath(
                        baseconfigs_location + os.sep + filename)
                ]
    except OSError:
        logging.warn(
            baseconfigs_location +
            ' is not accessible to get configs list')

    configs += [os.path.expanduser('~/.yandex-tank')]
    return configs


def is_ini(cfg_file):
    try:
        ConfigParser().read(cfg_file)
        return True
    except MissingSectionHeaderError:
        return False


def get_depr_cfg(config_files, no_rc, cmd_options, depr_options):
    try:
        all_config_files = []

        if not no_rc:
            all_config_files = get_default_configs()

        if not config_files:
            if os.path.exists(os.path.realpath('load.ini')):
                all_config_files += [os.path.realpath('load.ini')]
            elif os.path.exists(os.path.realpath('load.conf')):
                # just for old 'lunapark' compatibility
                conf_file = os.path.realpath('load.conf')
                all_config_files += [conf_file]
        else:
            for config_file in config_files:
                all_config_files.append(config_file)

        cfg_ini = load_ini_cfgs([cfg_file for cfg_file in all_config_files if is_ini(cfg_file)])

        # substitute telegraf config
        def patch_ini_config_with_monitoring(ini_config, mon_section_name):
            """
            :type ini_config: ConfigParser
            """
            CONFIG = 'config'
            if not ini_config.has_section(mon_section_name):
                raise NoOptionError
            telegraf_cfg = ini_config.get(mon_section_name, CONFIG)
            if not telegraf_cfg.startswith('<') and not telegraf_cfg.lower() == 'auto':
                with open(resource_manager.resource_filename(telegraf_cfg), 'rb') as telegraf_cfg_file:
                    config_contents = telegraf_cfg_file.read()
                ini_config.set(mon_section_name, CONFIG, config_contents)
            return ini_config

        try:
            cfg_ini = patch_ini_config_with_monitoring(cfg_ini, 'monitoring')
        except NoOptionError:
            try:
                patch_ini_config_with_monitoring(cfg_ini, 'telegraf')
            except NoOptionError:
                pass

        for section, key, value in depr_options:
            if not cfg_ini.has_section(section):
                cfg_ini.add_section(section)
            cfg_ini.set(section, key, value)
        return apply_shorthand_options(cfg_ini, cmd_options)
    except Exception as ex:
        sys.stderr.write(RealConsoleMarkup.RED)
        sys.stderr.write(RealConsoleMarkup.RESET)
        sys.stderr.write(RealConsoleMarkup.TOTAL_RESET)
        raise ex


def load_tank_core(config_files, cmd_options, no_rc, depr_options, *other_opts):
    other_opts = list(other_opts) if other_opts else []
    config_files = config_files if len(config_files) > 0 else [DEFAULT_CONFIG]
    if no_rc:
        configs = [load_cfg(cfg) for cfg in config_files] + other_opts + parse_options(cmd_options)
    else:
        configs = [load_core_base_cfg()] +\
            load_local_base_cfgs() +\
            [load_cfg(cfg) for cfg in config_files] + other_opts + parse_options(cmd_options)
    return TankCore(configs,
                    cfg_depr=get_depr_cfg(config_files, no_rc, cmd_options, depr_options))


class ConsoleTank:
    """    Worker class that runs tank core accepting cmdline params    """

    IGNORE_LOCKS = "ignore_locks"

    def __init__(self, options, ammofile):
        overwrite_options = {'core': {'lock_dir': options.lock_dir}} if options.lock_dir else {}
        self.options = options
        self.lock_dir = options.lock_dir if options.lock_dir else '/var/lock'
        self.baseconfigs_location = '/etc/yandex-tank'
        self.init_logging()
        self.log = logging.getLogger(__name__)

        if ammofile:
            self.log.debug("Ammofile: %s", ammofile)
            overwrite_options['phantom'] = {
                'use_caching': False,
                'ammofile': ammofile
            }

        self.core = load_tank_core(options.config, options.option, options.no_rc, [], overwrite_options)

        raw_cfg_file, raw_cfg_path = tempfile.mkstemp(suffix='_pre-validation-config.yaml')
        os.close(raw_cfg_file)
        self.core.config.save_raw(raw_cfg_path)
        self.core.add_artifact_file(raw_cfg_path)

        self.core.add_artifact_file(options.log)

        self.signal_count = 0
        self.scheduled_start = None

    def set_baseconfigs_dir(self, directory):
        """        Set directory where to read configs set        """
        self.baseconfigs_location = directory

    def init_logging(self):
        """ Set up logging, as it is very important for console tool """
        logger = logging.getLogger('')
        logger.setLevel(logging.DEBUG)
        log_filename = self.options.log
        # create file handler which logs even debug messages
        if log_filename:
            file_handler = logging.FileHandler(log_filename)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s [%(levelname)s] %(name)s %(filename)s:%(lineno)d\t%(message)s"
                ))
            logger.addHandler(file_handler)

        # create console handler with a higher log level
        console_handler = logging.StreamHandler(sys.stdout)
        stderr_hdl = logging.StreamHandler(sys.stderr)

        fmt_verbose = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s %(filename)s:%(lineno)d\t%(message)s"
        )
        fmt_regular = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")

        if self.options.verbose:
            console_handler.setLevel(logging.DEBUG)
            console_handler.setFormatter(fmt_verbose)
            stderr_hdl.setFormatter(fmt_verbose)
        elif self.options.quiet:
            console_handler.setLevel(logging.WARNING)
            console_handler.setFormatter(fmt_regular)
            stderr_hdl.setFormatter(fmt_regular)
        else:
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(fmt_regular)
            stderr_hdl.setFormatter(fmt_regular)

        f_err = SingleLevelFilter(logging.ERROR, True)
        f_warn = SingleLevelFilter(logging.WARNING, True)
        f_crit = SingleLevelFilter(logging.CRITICAL, True)
        console_handler.addFilter(f_err)
        console_handler.addFilter(f_warn)
        console_handler.addFilter(f_crit)
        logger.addHandler(console_handler)

        f_info = SingleLevelFilter(logging.INFO, True)
        f_debug = SingleLevelFilter(logging.DEBUG, True)
        stderr_hdl.addFilter(f_info)
        stderr_hdl.addFilter(f_debug)
        logger.addHandler(stderr_hdl)

    def configure(self):
        while True:
            try:
                self.core.get_lock(self.options.ignore_lock, self.lock_dir)
                break
            except LockError:
                if self.options.lock_fail:
                    raise RuntimeError("Lock file present, cannot continue")
                self.log.exception(
                    "Couldn't get lock. Will retry in 5 seconds...")
                time.sleep(5)
            except:
                self.core.release_lock()
                raise

        try:
            self.core.load_plugins()

            if self.options.scheduled_start:
                try:
                    self.scheduled_start = datetime.datetime.strptime(
                        self.options.scheduled_start, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    self.scheduled_start = datetime.datetime.strptime(
                        datetime.datetime.now().strftime('%Y-%m-%d ') +
                        self.options.scheduled_start, '%Y-%m-%d %H:%M:%S')

        except Exception as ex:
            self.log.info("Exception: %s", traceback.format_exc(ex))
            sys.stderr.write(RealConsoleMarkup.RED)
            self.log.error("%s", ex)
            sys.stderr.write(RealConsoleMarkup.RESET)
            sys.stderr.write(RealConsoleMarkup.TOTAL_RESET)
            self.core.release_lock()
            raise ex

    def __graceful_shutdown(self):
        """ call shutdown routines """
        retcode = 1
        self.log.info("Trying to shutdown gracefully...")
        retcode = self.core.plugins_end_test(retcode)
        retcode = self.core.plugins_post_process(retcode)
        self.log.info("Done graceful shutdown")
        return retcode

    def perform_test(self):
        """
        Run the test sequence via Tank Core
        """
        self.log.info("Performing test")
        retcode = 1
        try:
            self.core.plugins_configure()
            self.core.plugins_prepare_test()
            if self.scheduled_start:
                self.log.info(
                    "Waiting scheduled time: %s...", self.scheduled_start)
                while datetime.datetime.now() < self.scheduled_start:
                    self.log.debug(
                        "Not yet: %s < %s",
                        datetime.datetime.now(), self.scheduled_start)
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
            self.log.info(
                "Do not press Ctrl+C again, the test will be broken otherwise")
            sys.stdout.write(RealConsoleMarkup.RESET)
            sys.stdout.write(RealConsoleMarkup.TOTAL_RESET)
            self.signal_count += 1
            self.log.debug(
                "Caught KeyboardInterrupt: %s", traceback.format_exc(ex))
            try:
                retcode = self.__graceful_shutdown()
            except KeyboardInterrupt as ex:
                self.log.debug(
                    "Caught KeyboardInterrupt again: %s",
                    traceback.format_exc(ex))
                self.log.info(
                    "User insists on exiting, aborting graceful shutdown...")
                retcode = 1

        except Exception as ex:
            self.log.info("Exception: %s", traceback.format_exc(ex))
            sys.stderr.write(RealConsoleMarkup.RED)
            self.log.error("%s", ex)
            sys.stderr.write(RealConsoleMarkup.RESET)
            sys.stderr.write(RealConsoleMarkup.TOTAL_RESET)
            retcode = self.__graceful_shutdown()
            self.core.release_lock()
        finally:
            self.core.close()

        self.log.info("Done performing test with code %s", retcode)
        return retcode


class DevNullOpts:
    def __init__(self):
        pass

    log = "/dev/null"


class CompletionHelperOptionParser(OptionParser):
    def __init__(self):
        OptionParser.__init__(self, add_help_option=False)
        self.add_option(
            '--bash-switches-list',
            action='store_true',
            dest="list_switches",
            help="Options list")
        self.add_option(
            '--bash-options-prev',
            action='store',
            dest="list_options_prev",
            help="Options list")
        self.add_option(
            '--bash-options-cur',
            action='store',
            dest="list_options_cur",
            help="Options list")

    def error(self, msg):
        pass

    def exit(self, status=0, msg=None):
        pass

    def handle_request(self, parser):
        options = self.parse_args()[0]
        if options.list_switches:
            opts = []
            for option in parser.option_list:
                if "--bash" not in option.get_opt_string():
                    opts.append(option.get_opt_string())
            print(' '.join(opts))
            exit(0)

        if options.list_options_cur or options.list_options_prev:
            cmdtank = ConsoleTank(DevNullOpts(), None)
            cmdtank.core.load_configs(get_default_configs())
            cmdtank.core.load_plugins()

            opts = []
            for option in cmdtank.core.get_available_options():
                opts.append(cmdtank.core.SECTION + '.' + option + '=')

            plugin_keys = cmdtank.core.config.get_options(
                cmdtank.core.SECTION, cmdtank.core.PLUGIN_PREFIX)
            for (plugin_name, plugin_path) in plugin_keys:
                opts.append(
                    cmdtank.core.SECTION + '.' + cmdtank.core.PLUGIN_PREFIX +
                    plugin_name + '=')

            for plugin in cmdtank.core.plugins:
                for option in plugin.get_available_options():
                    opts.append(plugin.SECTION + '.' + option + '=')
            print(' '.join(sorted(opts)))
            exit(0)
