import ctypes
import logging
import os
import shutil
import time
from configparser import RawConfigParser, MissingSectionHeaderError
from multiprocessing import Manager, Event, Value, Process

import stat
import yaml

from yandextank.common.interfaces import TankInfo
from yandextank.common.util import Cleanup, Finish, Status
from yandextank.common.util import read_resource, TankapiLogFilter
from yandextank.config_converter.converter import convert_ini, convert_single_option
from yandextank.core import TankCore
from yandextank.core.tankcore import LockError, Lock
from yandextank.validator.validator import ValidationError

logger = logging.getLogger()


class TankWorker(Process):
    SECTION = 'core'
    FINISH_FILENAME = 'finish_status.yaml'
    DEFAULT_CONFIG = 'load.yaml'

    def __init__(self, configs, cli_options=None, cfg_patches=None, cli_args=None, no_local=False,
                 log_handlers=None, wait_lock=False, files=None, ammo_file=None,
                 debug=False, run_shooting_event=None, storage=None, resource_manager=None):
        super().__init__()
        self.interrupted = Event()
        manager = Manager()
        self.info = TankInfo(manager.dict())
        user_configs = self._combine_configs(configs, cli_options, cfg_patches, cli_args)
        self.core = TankCore(user_configs, self.interrupted, self.info, storage=storage, skip_base_cfgs=no_local, resource_manager=resource_manager)

        is_locked = Lock.is_locked(self.core.lock_dir)
        if is_locked and not self.core.config.get_option(self.SECTION, 'ignore_lock'):
            raise LockError(is_locked)

        self.wait_lock = wait_lock
        self.log_handlers = log_handlers if log_handlers is not None else []
        self.files = [] if files is None else files
        self.ammo_file = ammo_file
        self.config_paths = configs
        self.folder = self.core.artifacts_dir
        self.init_logging(debug or self.core.get_option(self.core.SECTION, 'debug'))

        self._status = Value(ctypes.c_char_p, Status.TEST_INITIATED)
        self._test_id = Value(ctypes.c_char_p, self.core.test_id.encode('utf8'))
        self._retcode = Value(ctypes.c_int, 0)
        self._msgs = manager.list()
        self._run_shooting_event = run_shooting_event or self._dummy_event()

    @staticmethod
    def _dummy_event():
        event = Event()
        event.set()
        return event

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
                if not self._run_shooting_event.is_set():
                    self.status = Status.TEST_WAITING_FOR_A_COMMAND_TO_RUN
                    self._wait_for_a_command_to_start_shooting()
                self.status = Status.TEST_RUNNING
                self.core.plugins_start_test()
                self.retcode = self.core.wait_for_finish()
                self._msgs.extend(self.core.errors)
            self.status = Status.TEST_POST_PROCESS
            self.retcode = self.core.plugins_post_process(self.retcode)

    def _wait_for_a_command_to_start_shooting(self):
        pool_timeout = 0.01
        while True:
            if self.core.interrupted.is_set():
                raise RuntimeError('Test stopped before shooting started.')
            if self._run_shooting_event.wait(pool_timeout):
                return

    @staticmethod
    def _combine_configs(run_cfgs, cli_options, cfg_patches, cli_args):
        if cli_options is None:
            cli_options = []
        if cfg_patches is None:
            cfg_patches = []
        if cli_args is None:
            cli_args = []
        run_cfgs = run_cfgs if len(run_cfgs) > 0 else [TankWorker.DEFAULT_CONFIG]
        return (
            [load_cfg(cfg) for cfg in run_cfgs] +
            parse_options(cli_options) +
            parse_and_check_patches(cfg_patches) +
            cli_args
        )

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
                self.add_msgs(str(e))
                if not self.wait_lock:
                    raise RuntimeError("Lock file present, cannot continue")
                logger.warning(
                    "Couldn't get lock. Will retry in 5 seconds...")
                time.sleep(5)
        else:
            raise KeyboardInterrupt
        return lock

    @property
    def msg(self):
        return '\n'.join(self._msgs)

    def add_msgs(self, *msgs):
        self._msgs.extend(msgs)

    @property
    def test_id(self):
        with self._test_id.get_lock():
            return self._test_id.value.decode('utf8')

    @property
    def status(self):
        with self._status.get_lock():
            return self._status.value

    @status.setter
    def status(self, val):
        with self._status.get_lock():
            self._status.value = val

    @property
    def retcode(self):
        with self._retcode.get_lock():
            return self._retcode.value

    @retcode.setter
    def retcode(self, val):
        with self._retcode.get_lock():
            self._retcode.value = val

    def collect_files(self):
        for cfg in self.config_paths:
            shutil.move(cfg, self.folder)
        for f in self.files:
            shutil.move(f, self.folder)
        if self.ammo_file:
            shutil.move(self.ammo_file, self.folder)

    def go_to_test_folder(self):
        os.chdir(self.folder)


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


def is_ini(cfg_file):
    if cfg_file.endswith('.yaml') or cfg_file.endswith('.json'):
        return False
    try:
        RawConfigParser().read(cfg_file)
        return True
    except MissingSectionHeaderError:
        return False
