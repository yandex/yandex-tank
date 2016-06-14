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
            "enable_full_log" : "adb %s shell dumpsys batterystats --enable full-wake-history",
            "disable_full_log" : "adb %s shell dumpsys batterystats --disable full-wake-history",
            "reset" : "adb %s shell dumpsys batterystats --reset",
            "dump": "adb %s shell dumpsys batterystats"
        }

    def get_available_options(self):
        return ["device_id"]

    def configure(self):
        self.device_id = self.get_option("device_id", None).strip()
        if not self.device_id:
            modify = ''
        else:
            modify = '-s {device_id}'.format(device_id=self.device_id)
        for key, value in self.cmds.iteritems():
            self.cmds[key] = value % modify

        self.logfile = self.core.mkstemp(".log", "battery_historian_")
        self.core.add_artifact_file(self.logfile)

    def prepare_test(self):
        out = subprocess.check_output(self.cmds['enable_full_log'], shell=True)
        out = subprocess.check_output(self.cmds['reset'], shell=True)

    def end_test(self, retcode):
        out = subprocess.Popen(self.cmds['dump'], stdout=subprocess.PIPE, shell=True).communicate()[0]
        subprocess.check_output(self.cmds['disable_full_log'], shell=True)
        subprocess.check_output(self.cmds['reset'], shell=True)
        with open(self.logfile, 'w') as f:
            f.write(out)
        return retcode

    def is_test_finished(self):
        return -1
