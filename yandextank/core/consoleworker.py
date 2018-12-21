""" Provides classes to run TankCore from console environment """
import fnmatch
import glob
import logging
import os
import shutil
import signal
import stat
import sys
import time
import traceback
from ConfigParser import ConfigParser, MissingSectionHeaderError, NoOptionError, NoSectionError
from threading import Thread, Event

import yaml
from netort.resource import manager as resource_manager
from pkg_resources import resource_filename

from yandextank.validator.validator import ValidationError
from .tankcore import TankCore, LockError, Lock
from ..config_converter.converter import convert_ini, convert_single_option

DEFAULT_CONFIG = 'load.yaml'
logger = logging.getLogger()


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


def signal_handler(sig, frame):
    """ required for non-tty python runs to interrupt """
    raise KeyboardInterrupt()


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def load_cfg(cfg_filename):
    """

    :type cfg_filename: str
    """
    if is_ini(cfg_filename):
        return convert_ini(cfg_filename)
    else:
        with open(cfg_filename) as f:
            return yaml.load(f)


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
            in [option.split('=', 1) for option in options]
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
        logger.info(
            baseconfigs_location + ' is not accessible to get configs list')

    configs += [os.path.expanduser('~/.yandex-tank')]
    return configs


def is_ini(cfg_file):
    if cfg_file.endswith('.yaml') or cfg_file.endswith('.json'):
        return False
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


def parse_and_check_patches(patches):
    parsed = [yaml.load(p) for p in patches]
    for patch in parsed:
        if not isinstance(patch, dict):
            raise ValidationError('Config patch "{}" should be a dict'.format(patch))
    return parsed


class Cleanup:
    def __init__(self, tankworker):
        """

        :type tankworker: TankWorker
        """
        self._actions = []
        self.tankworker = tankworker

    def add_action(self, name, fn):
        """

        :type fn: function
        :type name: str
        """
        assert callable(fn)
        self._actions.append((name, fn))

    def __enter__(self):
        self.tankworker.init_folder()
        return self.add_action

    def __exit__(self, exc_type, exc_val, exc_tb):
        msgs = []
        if exc_type:
            msg = 'Exception occurred:\n{}: {}\n{}'.format(exc_type, exc_val, '\n'.join(traceback.format_tb(exc_tb)))
            msgs.append(msg)
            logger.error(msg)
        logger.info('Trying to clean up')
        for name, action in reversed(self._actions):
            try:
                action()
            except Exception:
                msg = 'Exception occurred during cleanup action {}'.format(name)
                msgs.append(msg)
                logger.error(msg, exc_info=True)
        self.tankworker.save_status('\n'.join(msgs))
        self.tankworker.core._collect_artifacts()
        return False  # re-raise exception


class Finish:
    def __init__(self, tankworker):
        """
        :type tankworker: TankWorker
        """
        self.worker = tankworker

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.worker.status = Status.TEST_FINISHING
        retcode = self.worker.retcode
        if exc_type:
            logger.error('Test interrupted:\n{}: {}\n{}'.format(exc_type, exc_val, exc_tb))
            retcode = 1
        retcode = self.worker.core.plugins_end_test(retcode)
        self.worker.retcode = retcode
        return True  # swallow exception & proceed to post-processing


class Status():
    TEST_POST_PROCESS = 'POST_PROCESS'
    TEST_INITIATED = 'INITIATED'
    TEST_PREPARING = "PREPARING"
    TEST_NOT_FOUND = "NOT_FOUND"
    TEST_RUNNING = "RUNNING"
    TEST_FINISHING = "FINISHING"
    TEST_FINISHED = "FINISHED"


class TankWorker(Thread):
    SECTION = 'core'
    FINISH_FILENAME = 'finish_status.yaml'

    def __init__(self, configs, cli_options=None, cfg_patches=None, cli_args=None, no_local=False,
                 log_handlers=None, wait_lock=True, files=None, ammo_file=None, api_start=False):
        super(TankWorker, self).__init__()
        self.api_start = api_start
        self.wait_lock = wait_lock
        self.log_handlers = log_handlers if log_handlers is not None else []
        self.files = [] if files is None else files
        self.ammo_file = ammo_file

        self.interrupted = Event()
        self.config_list = self._combine_configs(configs, cli_options, cfg_patches, cli_args, no_local)
        self.core = TankCore(self.config_list, self.interrupted)
        self.status = Status.TEST_INITIATED
        self.test_id = self.core.test_id
        self.retcode = None
        self.msg = ''

    @staticmethod
    def _combine_configs(run_cfgs, cli_options=None, cfg_patches=None, cli_args=None, no_local=False):
        if cli_options is None:
            cli_options = []
        if cfg_patches is None:
            cfg_patches = []
        if cli_args is None:
            cli_args = []
        run_cfgs = run_cfgs if len(run_cfgs) > 0 else [DEFAULT_CONFIG]

        if no_local:
            configs = [load_cfg(cfg) for cfg in run_cfgs] + \
                parse_options(cli_options) + \
                parse_and_check_patches(cfg_patches) + \
                cli_args
        else:
            configs = [load_core_base_cfg()] + \
                load_local_base_cfgs() + \
                [load_cfg(cfg) for cfg in run_cfgs] + \
                parse_options(cli_options) + \
                parse_and_check_patches(cfg_patches) + \
                cli_args
        return configs

    def init_folder(self):
        self.folder = self.core.artifacts_dir
        if self.api_start > 0:
            for f in self.files:
                shutil.move(f, self.folder)
            if self.ammo_file:
                shutil.move(self.ammo_file, self.folder)
            os.chdir(self.folder)

    def run(self):
        with Cleanup(self) as add_cleanup:
            lock = self.get_lock()
            add_cleanup('release lock', lock.release)
            self.status = Status.TEST_PREPARING
            self.init_logging(debug=True)
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
            self.status = Status.TEST_FINISHED

    def stop(self):
        self.interrupted.set()
        self.core.interrupt()

    def get_status(self):
        return {'status_code': self.status,
                'left_time': None,
                'exit_code': self.retcode if self.status is Status.TEST_FINISHED else None,
                'lunapark_id': self.get_lunapark_jobno(),
                'tank_msg': self.msg,
                'lunapark_url': self.get_lunapark_link()}

    def save_status(self, msg):
        self.msg = msg
        self.status = Status.TEST_FINISHED
        with open(os.path.join(self.folder, self.FINISH_FILENAME), 'w') as f:
            yaml.dump(self.get_status(), f)

    def get_lunapark_jobno(self):
        try:
            return str(self.core.status['uploader']['job_no'])
        except KeyError:
            logger.warning('Job number is not available yet')
            return None

    def get_lunapark_link(self):
        try:
            return str(self.core.status['uploader']['web_link'])
        except KeyError:
            logger.warning('Job number is not available yet')
            return None

    def init_logging(self, debug=False):

        filename = os.path.join(self.core.artifacts_dir, 'tank.log')
        open(filename, 'a').close()
        current_file_mode = os.stat(filename).st_mode
        os.chmod(filename, current_file_mode | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

        logger.handlers = []
        logger.setLevel(logging.DEBUG if debug else logging.INFO)

        file_handler = logging.FileHandler(filename)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s %(filename)s:%(lineno)d\t%(message)s"))
        file_handler.addFilter(TankapiLogFilter())
        logger.addHandler(file_handler)
        logger.info("Log file created")

        for handler in self.log_handlers:
            logger.addHandler(handler)
            logger.info("Logging handler {} added".format(handler))

    def get_lock(self):
        while not self.interrupted.is_set():
            try:
                lock = Lock(self.test_id, self.folder).acquire(self.core.lock_dir,
                                                               self.core.config.get_option(self.SECTION, 'ignore_lock'))
                self.set_msg('')
                break
            except LockError as e:
                self.set_msg(e.message)
                if not self.wait_lock:
                    raise RuntimeError("Lock file present, cannot continue")
                logger.warning(
                    "Couldn't get lock. Will retry in 5 seconds...")
                time.sleep(5)
        else:
            raise KeyboardInterrupt
        return lock

    def set_msg(self, msg):
        self.msg = msg


class TankapiLogFilter(logging.Filter):
    def filter(self, record):
        return record.name != 'tankapi'


class DevNullOpts:
    def __init__(self):
        pass

    log = "/dev/null"
