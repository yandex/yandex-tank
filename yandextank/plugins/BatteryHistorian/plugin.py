''' Module that collects android device battery usage '''

import logging
import subprocess

from ...common.interfaces import AbstractPlugin

logger = logging.getLogger(__name__)


class Plugin(AbstractPlugin):
    """ Plugin that collects android device battery usage """
    SECTION = "battery_historian"

    @staticmethod
    def get_key():
        return __file__

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.logfile = None
        self.default_target = None
        self.device_id = None
        self.cmds = {
            "enable_full_log":
            "adb %s shell dumpsys batterystats --enable full-wake-history",
            "disable_full_log":
            "adb %s shell dumpsys batterystats --disable full-wake-history",
            "reset": "adb %s shell dumpsys batterystats --reset",
            "dump": "adb %s shell dumpsys batterystats"
        }

    def get_available_options(self):
        return ["device_id"]

    def configure(self):
        self.device_id = self.get_option("device_id", None).strip()
        if self.device_id:
            modify = '-s {device_id}'.format(device_id=self.device_id)
            for key, value in self.cmds.iteritems():
                self.cmds[key] = value % modify
            self.logfile = self.core.mkstemp(".log", "battery_historian_")
            self.core.add_artifact_file(self.logfile)

    def prepare_test(self):
        if self.device_id:
            try:
                out = subprocess.check_output(
                    self.cmds['enable_full_log'], shell=True)
                logger.debug('Enabling full-log: %s', out)
                out = subprocess.check_output(self.cmds['reset'], shell=True)
                logger.debug('Reseting battery stats: %s', out)
            except subprocess.CalledProcessError:
                logger.error(
                    'Error trying to prepare battery historian plugin',
                    exc_info=True)

    def end_test(self, retcode):
        if self.device_id:
            try:
                logger.debug('dumping battery stats')
                dump = subprocess.Popen(
                    self.cmds['dump'], stdout=subprocess.PIPE,
                    shell=True).communicate()[0]
                out = subprocess.check_output(
                    self.cmds['disable_full_log'], shell=True)
                logger.debug('Disabling fulllog: %s', out)
                out = subprocess.check_output(self.cmds['reset'], shell=True)
                logger.debug('Battery stats reset: %s', out)
            except subprocess.CalledProcessError:
                logger.error(
                    'Error trying to collect battery historian plugin data',
                    exc_info=True)
            with open(self.logfile, 'w') as f:
                f.write(dump)
        return retcode

    def is_test_finished(self):
        return -1
