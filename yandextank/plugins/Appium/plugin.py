import logging
import subprocess
import time

from ...common.interfaces import AbstractPlugin

logger = logging.getLogger(__name__)


class Plugin(AbstractPlugin):
    ''' Start appium before the test, stop after it ended '''

    SECTION = "appium"

    def __init__(self, core):
        super(Plugin, self).__init__(core)
        self.appium_cmd = None
        self.appium_log = None
        self.appium_port = None
        self.process_stdout = None

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        opts = ["appium_cmd"]
        return opts

    def configure(self):
        # plugin part
        self.appium_cmd = self.get_option("appium_cmd", "appium")
        self.appium_user = self.get_option("user", "")
        self.appium_port = self.get_option("port", "4723")
        self.appium_log = self.core.mkstemp(".log", "appium_")
        self.core.add_artifact_file(self.appium_log)

    def prepare_test(self):
        args = [self.appium_cmd, '-p', self.appium_port, '-g', self.appium_log]
        if self.appium_user:
            args = ["su", "-c", " ".join(args), self.appium_user]
        logger.info("Starting appium server: %s", args)
        self.process_start_time = time.time()
        process_stdout_file = self.core.mkstemp(".log", "appium_stdout_")
        self.core.add_artifact_file(process_stdout_file)
        self.process_stdout = open(process_stdout_file, 'w')
        self.process = subprocess.Popen(
            args,
            stderr=self.process_stdout,
            stdout=self.process_stdout,
            close_fds=True)
        logger.info("Waiting 5 seconds for Appium to start...")
        time.sleep(5)

    def is_test_finished(self):
        retcode = self.process.poll()
        if retcode is not None:
            logger.warning("Appium exited: %s", retcode)
            return abs(retcode)
        else:
            return -1

    def end_test(self, retcode):
        if self.process and self.process.poll() is None:
            logger.info(
                "Terminating appium process with PID %s", self.process.pid)
            self.process.terminate()
            if self.process_stdout:
                self.process_stdout.close()
        else:
            logger.warn("Appium finished unexpectedly")
        return retcode

    def get_info(self):
        return None
