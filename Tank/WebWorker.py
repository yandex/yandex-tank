import ctypes
import inspect
import logging
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


class PrepareThread(InterruptibleThread):
    def __init__(self, core, config):
        """

        :type core: tankcore.TankCore
        """
        super(PrepareThread, self).__init__()
        self.daemon = True
        self.core = core
        self.config = config


    def run(self):
        logging.info("Starting prepare")
        self.core.load_configs([self.config])
        self.core.load_plugins()
        self.core.plugins_configure()
        self.core.plugins_prepare_test()


class TestRunThread(InterruptibleThread):
    def __init__(self, core, config):
        """

        :type core: tankcore.TankCore
        """
        super(TestRunThread, self).__init__()
        self.daemon = True
        self.core = core
        self.config = config

    def run(self):
        logging.info("Starting test")
        self.core.plugins_start_test()
        retcode = self.core.wait_for_finish()
        retcode = self.core.plugins_end_test(retcode)
        retcode = self.core.plugins_post_process(retcode)

