import glob
import logging
import os
import shutil
import stat
import time
from configparser import RawConfigParser, MissingSectionHeaderError
from multiprocessing import Event as ProcessEvent
from threading import Event as ThreadEvent

import yaml
from pkg_resources import resource_filename

from yandextank.common.interfaces import TankInfo
from yandextank.common.util import read_resource, TankapiLogFilter
from yandextank.config_converter.converter import convert_ini, convert_single_option
from yandextank.core import TankCore
from yandextank.core.tankcore import LockError, Lock
from yandextank.validator.validator import ValidationError

logger = logging.getLogger()


class TankWorker():
    SECTION = 'core'
    FINISH_FILENAME = 'finish_status.yaml'
    DEFAULT_CONFIG = 'load.yaml'

    def __init__(self, configs, cli_options=None, cfg_patches=None, cli_args=None, no_local=False,
                 log_handlers=None, wait_lock=False, files=None, ammo_file=None, api_start=False, manager=None,
                 debug=False):
        self.api_start = api_start
        self.wait_lock = wait_lock
        self.log_handlers = log_handlers if log_handlers is not None else []
        self.files = [] if files is None else files
        self.ammo_file = ammo_file
        self.config_paths = configs
        self.interrupted = ProcessEvent() if api_start else ThreadEvent()
        self.info = TankInfo(manager.dict()) if api_start else TankInfo(dict())
        self.config_list = self._combine_configs(configs, cli_options, cfg_patches, cli_args, no_local)
        self.core = TankCore(self.config_list, self.interrupted, self.info)
        self.folder = self.init_folder()
        self.init_logging(debug or self.core.get_option(self.core.SECTION, 'debug'))

        is_locked = Lock.is_locked(self.core.lock_dir)
        if is_locked and not self.core.config.get_option(self.SECTION, 'ignore_lock'):
            raise LockError(is_locked)

    @staticmethod
    def _combine_configs(run_cfgs, cli_options=None, cfg_patches=None, cli_args=None, no_local=False):
        if cli_options is None:
            cli_options = []
        if cfg_patches is None:
            cfg_patches = []
        if cli_args is None:
            cli_args = []
        run_cfgs = run_cfgs if len(run_cfgs) > 0 else [TankWorker.DEFAULT_CONFIG]

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
        folder = self.core.artifacts_dir
        if self.api_start > 0:
            for cfg in self.config_paths:
                shutil.move(cfg, folder)
            for f in self.files:
                shutil.move(f, folder)
            if self.ammo_file:
                shutil.move(self.ammo_file, folder)
            os.chdir(folder)
        return folder

    def stop(self):
        self.interrupted.set()
        logger.warning('Interrupting')

    def get_status(self):
        return {'status_code': self.status.decode('utf8'),
                'left_time': None,
                'exit_code': self.retcode,
                'lunapark_id': self.get_info('uploader', 'job_no'),
                'tank_msg': self.msg,
                'test_id': self.test_id,
                'lunapark_url': self.get_info('uploader', 'web_link')
                }

    def save_finish_status(self):
        with open(os.path.join(self.folder, self.FINISH_FILENAME), 'w') as f:
            yaml.safe_dump(self.get_status(), f, encoding='utf-8', allow_unicode=True)

    def get_info(self, section_name, key_name):
        return self.info.get_value([section_name, key_name])

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
                break
            except LockError as e:
                self.upd_msg(e.message)
                if not self.wait_lock:
                    raise RuntimeError("Lock file present, cannot continue")
                logger.warning(
                    "Couldn't get lock. Will retry in 5 seconds...")
                time.sleep(5)
        else:
            raise KeyboardInterrupt
        return lock

    def upd_msg(self, msg):
        if msg:
            self.msg = self.msg + '\n' + msg


def load_cfg(cfg_filename):
    """

    :type cfg_filename: str
    """
    if is_ini(cfg_filename):
        return convert_ini(cfg_filename)
    else:
        cfg_yaml = yaml.load(read_resource(cfg_filename), Loader=yaml.FullLoader)
        if not isinstance(cfg_yaml, dict):
            raise ValidationError('Wrong config format, should be a yaml')
        return cfg_yaml


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


def parse_and_check_patches(patches):
    parsed = [yaml.load(p, Loader=yaml.FullLoader) for p in patches]
    for patch in parsed:
        if not isinstance(patch, dict):
            raise ValidationError('Config patch "{}" should be a dict'.format(patch))
    return parsed


def cfg_folder_loader(path):
    """
    :type path: str
    """
    CFG_WILDCARD = '*.yaml'
    return [load_cfg(filename) for filename in sorted(glob.glob(os.path.join(path, CFG_WILDCARD)))]


def is_ini(cfg_file):
    if cfg_file.endswith('.yaml') or cfg_file.endswith('.json'):
        return False
    try:
        RawConfigParser().read(cfg_file)
        return True
    except MissingSectionHeaderError:
        return False
