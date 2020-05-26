# -*- coding: utf-8 -*-
""" Provides class to run TankCore from python """
import ctypes
import logging
from multiprocessing import Value
from multiprocessing.process import Process

from yandextank.common.util import Cleanup, Finish, Status
from yandextank.core.tankworker import TankWorker

logger = logging.getLogger()


class ApiWorker(Process, TankWorker):
    SECTION = 'core'
    FINISH_FILENAME = 'finish_status.yaml'

    def __init__(self, configs, cli_options=None, cfg_patches=None, cli_args=None, no_local=False,
                 log_handlers=None, wait_lock=False, files=None, ammo_file=None):
        Process.__init__(self)
        TankWorker.__init__(self, configs=configs, cli_options=cli_options, cfg_patches=cfg_patches,
                            cli_args=cli_args, no_local=no_local, log_handlers=log_handlers,
                            wait_lock=wait_lock, files=files, ammo_file=ammo_file, api_start=True)
        self._status = Value(ctypes.c_char_p, Status.TEST_INITIATED)
        self._test_id = Value(ctypes.c_char_p, self.core.test_id)
        self._retcode = None
        self._msg = Value(ctypes.c_char_p, '')

    @property
    def test_id(self):
        return self._test_id.value

    @property
    def status(self):
        return self._status.value

    @status.setter
    def status(self, val):
        self._status.value = val

    @property
    def retcode(self):
        return self._retcode.value if self._retcode is not None else None

    @retcode.setter
    def retcode(self, val):
        if self._retcode is None:
            self._retcode = Value(ctypes.c_int, val)
        else:
            self._retcode.value = val

    @property
    def msg(self):
        return self._msg.value

    @msg.setter
    def msg(self, val):
        self._msg.value = val

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
