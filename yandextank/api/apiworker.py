# -*- coding: utf-8 -*-
""" Provides class to run TankCore from python """
import ctypes
import logging
from multiprocessing import Value, Process

from yandextank.common.util import Status
from yandextank.core.tankworker import TankWorker

logger = logging.getLogger()


class ApiWorker(Process, TankWorker):
    SECTION = 'core'
    FINISH_FILENAME = 'finish_status.yaml'

    def __init__(self, manager, config_paths, cli_options=None, cfg_patches=None, cli_args=None, no_local=False,
                 log_handlers=None, wait_lock=False, files=None, ammo_file=None):
        Process.__init__(self)
        TankWorker.__init__(self, configs=config_paths, cli_options=cli_options, cfg_patches=cfg_patches,
                            cli_args=cli_args, no_local=no_local, log_handlers=log_handlers,
                            wait_lock=wait_lock, files=files, ammo_file=ammo_file, api_start=True, manager=manager)
        self._status = Value(ctypes.c_char_p, Status.TEST_INITIATED)
        self._test_id = Value(ctypes.c_char_p, self.core.test_id.encode('utf8'))
        self._retcode = Value(ctypes.c_int, 0)
        self._msgs = manager.list()

    def run(self):
        return self._run()

    @property
    def test_id(self):
        return self._test_id.value.decode('utf8')

    @property
    def status(self):
        self._status.acquire()
        res = self._status.value
        self._status.release()
        return res

    @status.setter
    def status(self, val):
        self._status.acquire()
        self._status.value = val
        self._status.release()

    @property
    def retcode(self):
        return self._retcode.value

    @retcode.setter
    def retcode(self, val):
        self._retcode.value = val


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
