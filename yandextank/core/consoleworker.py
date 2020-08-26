""" Provides classes to run TankCore from console environment """
import fnmatch
import logging
import os
import signal
import sys
from configparser import RawConfigParser, NoOptionError, NoSectionError
from threading import Thread

from netort.resource import manager as resource_manager
from pkg_resources import resource_filename

from yandextank.common.util import Cleanup, Finish, Status
from yandextank.core.tankworker import TankWorker, is_ini

logger = logging.getLogger()


class RealConsoleMarkup(object):
    '''
    Took colors from here: https://www.siafoo.net/snippet/88
    '''
    WHITE_ON_BLACK = '\033[37;40m'
    TOTAL_RESET = '\033[0m'
    clear = "\x1b[2J\x1b[H"
    new_line = "\n"

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


def signal_handler(sig, frame):
    """ required for non-tty python runs to interrupt """
    raise KeyboardInterrupt()


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


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
    cfg = RawConfigParser()
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
        logger.info(
            baseconfigs_location + ' is not accessible to get configs list')

    configs += [os.path.expanduser('~/.yandex-tank')]
    return configs


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
            telegraf_cfg = ini_config.get(mon_section_name, CONFIG)
            if not telegraf_cfg.startswith('<') and not telegraf_cfg.lower() == 'auto':
                with open(resource_manager.resource_filename(telegraf_cfg), 'rb') as telegraf_cfg_file:
                    config_contents = telegraf_cfg_file.read()
                ini_config.set(mon_section_name, CONFIG, config_contents)
            return ini_config

        try:
            cfg_ini = patch_ini_config_with_monitoring(cfg_ini, 'monitoring')
        except (NoSectionError, NoOptionError):
            try:
                patch_ini_config_with_monitoring(cfg_ini, 'telegraf')
            except (NoOptionError, NoSectionError):
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


class ConsoleWorker(Thread, TankWorker):
    def __init__(self, configs, cli_options=None, cfg_patches=None, cli_args=None, no_local=False,
                 log_handlers=None, wait_lock=False, files=None, ammo_file=None, debug=False):
        Thread.__init__(self)
        TankWorker.__init__(self, configs=configs, cli_options=cli_options, cfg_patches=cfg_patches,
                            cli_args=cli_args, no_local=no_local, log_handlers=log_handlers,
                            wait_lock=wait_lock, files=files, ammo_file=ammo_file, debug=debug)
        self.daemon = True
        self.status = Status.TEST_INITIATED
        self.test_id = self.core.test_id
        self.retcode = None
        self.msg = ''

    def run(self):
        with Cleanup(self) as add_cleanup:
            lock = self.get_lock()
            add_cleanup('release lock', lock.release)
            self.status = Status.TEST_PREPARING
            logger.info('Created a folder for the test. %s' % self.folder)
            self.core.plugins_configure()
            add_cleanup('plugins cleanup', self.core.plugins_cleanup)
            self.core.plugins_prepare_test()
            with Finish(self):
                self.status = Status.TEST_RUNNING
                self.core.plugins_start_test()
                self.retcode = self.core.wait_for_finish()
            self.status = Status.TEST_POST_PROCESS
            self.retcode = self.core.plugins_post_process(self.retcode)


class DevNullOpts:
    def __init__(self):
        pass

    log = "/dev/null"
