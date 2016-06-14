''' Module that collects android device battery usage '''

import logging
import subprocess
import shlex

from ...core.interfaces import AbstractPlugin

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
            "enable_full_log" : shlex.split("adb shell dumpsys batterystats --enable full-wake-history"),
            "disable_full_log" : shlex.split("adb shell dumpsys batterystats --disable full-wake-history"),
            "reset" : shlex.split("adb shell dumpsys batterystats --reset"),
            "dump": shlex.split("adb shell dumpsys batterystats")
        }

    def get_available_options(self):
        return ["device_id"]

    def configure(self):
        self.device_id = self.get_option("device_id", None).strip()
        if self.device_id:
            for key, value in self.cmds.iteritems():
                self.cmds['key'] = "{origin} -s {device_id}".format(
                    origin=value,
                    device_id=self.device_id
                )
            logger.debug('cmds with device_ids: %s', self.cmds)

        self.logfile = self.core.mkstemp(".log", "battery_historian_")
        self.core.add_artifact_file(self.logfile)

    def prepare_test(self):
        subprocess.call(self.cmds['enable_full_log'], shell=True)
        subprocess.call(self.cmds['reset'], shell=True)

    def end_test(self, retcode):
        out = subprocess.Popen(self.cmds['dump'], stdout=subprocess.PIPE).communicate()[0]
        subprocess.call(self.cmds['disable_full_log'], shell=True)
        subprocess.call(self.cmds['reset'], shell=True)
        with open(self.logfile, 'w') as f:
            f.write(out)
        return retcode

    def is_test_finished(self):
        return -1
