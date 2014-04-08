import ctypes
import inspect
import logging
import os
from threading import Thread
import threading


class InterruptibleThread(Thread):
    def __async_raise(self, tid, exctype):
        """Raises an exception in the threads with id tid"""
        #http://stackoverflow.com/questions/323972/is-there-any-way-to-kill-a-thread-in-python
        if not inspect.isclass(exctype):
            raise TypeError("Only types can be raised (not instances)")
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid,
                                                         ctypes.py_object(exctype))
        if res == 0:
            raise ValueError("invalid thread id")
        elif res != 1:
            # "if it returns a number greater than one, you're in trouble,
            # and you should call it again with exc=NULL to revert the effect"
            ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, 0)
            raise SystemError("PyThreadState_SetAsyncExc failed")

    def __get_my_tid(self):
        """determines this (self's) thread id

        CAREFUL : this function is executed in the context of the caller
        thread, to get the identity of the thread represented by this
        instance.
        """
        if not self.isAlive():
            raise threading.ThreadError("the thread is not active")

        # do we have it cached?
        if hasattr(self, "_thread_id"):
            return self._thread_id

        # no, look for it in the _active dict
        for tid, tobj in threading._active.items():
            if tobj is self:
                self._thread_id = tid
                return tid

        raise AssertionError("could not determine the thread's id")

    def interrupt(self):
        logging.info("Interrupting the thread")
        self.__async_raise(self.__get_my_tid(), KeyboardInterrupt())


class AbstractTankThread(InterruptibleThread):
    def __init__(self, core, cwd):
        """

        :type core: tankcore.TankCore
        """
        super(AbstractTankThread, self).__init__()
        os.chdir(cwd)
        self.daemon = True
        self.core = core
        self.retcode = -1

    def graceful_shutdown(self):
        self.retcode = self.core.plugins_end_test(self.retcode)
        self.retcode = self.core.plugins_post_process(self.retcode)


class PrepareThread(AbstractTankThread):
    def __init__(self, core, config):
        """

        :type core: tankcore.TankCore
        """
        super(PrepareThread, self).__init__(core, os.path.dirname(config))
        self.config = config


    def run(self):
        logging.info("Starting prepare")
        try:
            self.core.load_configs([self.config])
            self.core.load_plugins()
            self.core.plugins_configure()
            self.core.plugins_prepare_test()
            self.retcode = 0
        except Exception, exc:
            self.retcode = 1
            self.graceful_shutdown()


class TestRunThread(AbstractTankThread):
    def run(self):
        logging.info("Starting test")
        try:
            self.core.plugins_start_test()
            self.retcode = self.core.wait_for_finish()
        except Exception, exc:
            self.retcode = 1
        finally:
            self.graceful_shutdown()

