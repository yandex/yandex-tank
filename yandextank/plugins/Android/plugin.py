import logging
import subprocess
import time
import urllib
import sys
import glob

from ...common.interfaces import AbstractPlugin, GeneratorPlugin
from .reader import AndroidReader, AndroidStatsReader

logger = logging.getLogger(__name__)


class Plugin(AbstractPlugin, GeneratorPlugin):

    SECTION = "android"

    def __init__(self, core):
        super(Plugin, self).__init__(core)
        self.apk = None
        self.test = None
        self.clazz = None
        self.package = None
        self.process_test = None
        self.process_grabber = None
        self.apk_path = "./app.apk"
        self.test_path = "./app-test.apk"
        self.lightning_path = "./lightning.apk"
        self.grab_log = "./output.bin"
        self.event_log = "./events.log"
        self.device = None

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        opts = ["package", "apk", "test", "class"]
        return opts

    def configure(self):
        # plugin part
        self.apk = self.get_option("apk")
        self.test = self.get_option("test")
        self.clazz = self.get_option("class")
        self.package = self.get_option("package")

    def prepare_test(self):
        aggregator = self.core.job.aggregator_plugin

        if aggregator:
            aggregator.reader = AndroidReader()
            aggregator.stats_reader = AndroidStatsReader()

        ports = None
        logger.info("Trying to find device")
        if sys.platform.startswith('linux'):
            ports = glob.glob('/dev/ttyUSB[0-9]*')
        elif sys.platform.startswith('darwin'):
            ports = glob.glob('/dev/cu.wchusbserial[0-9]*')
        else:
            print 'Your OS is not supported yet'

        logger.info("Ports = " + ''.join(ports))
        try:
            self.device = [port for port in ports if 'Bluetooth' not in port][0]
            logger.info("Found device = " + self.device)
        except Exception:
            logger.info("Device not found")

        logger.info("Download lightning...")
        urllib.urlretrieve("http://storage-int.mdst.yandex.net:80/get-pogoda/4268/lightning.apk", self.lightning_path)

        logger.info("Download apk...")
        urllib.urlretrieve(self.apk, self.apk_path)

        logger.info("Download test...")
        urllib.urlretrieve(self.test, self.test_path)

        logger.info("Uninstall the lightning...")
        subprocess.check_output(["adb", "uninstall", "net.yandex.overload.lightning"])

        logger.info("Uninstall the app...")
        subprocess.check_output(["adb", "uninstall", self.package])

        logger.info("Uninstall the test...")
        subprocess.check_output(["adb", "uninstall", '{}.test'.format(self.package)])

        logger.info("Install the lightning...")
        subprocess.check_output(["adb", "install", self.lightning_path])

        logger.info("Install the apk...")
        subprocess.check_output(["adb", "install", self.apk_path])

        logger.info("Install the test...")
        subprocess.check_output(["adb", "install", self.test_path])

        logger.info("Clear logcat...")
        subprocess.check_output(["adb", "logcat", "-c"])

    def start_test(self):
        if self.device:
            logger.info("Start grabber...")
            self.process_grabber = subprocess.Popen(
                ["/usr/local/bin/volta-grab", "--device", self.device, "--seconds", "10800", "--output", self.grab_log])

        logger.info("Start flashlight...")
        subprocess.Popen(["adb", "shell", "am", "start", "-n",
                          "net.yandex.overload.lightning/net.yandex.overload.lightning.MainActivity"])
        time.sleep(12)

        args = ["adb", "shell", "am", "instrument", "-w", "-e", "class", self.clazz, '{}.test/android.support.test.runner.AndroidJUnitRunner'.format(self.package)]
        logger.info("Starting: %s", args)
        self.process_test = subprocess.Popen(
            args)

    def is_test_finished(self):
        retcode = self.process_test.poll()
        if retcode is not None:
            logger.info("Subprocess done its work with exit code: %s", retcode)
            return abs(retcode)
        else:
            return -1

    def end_test(self, retcode):
        if self.device:
            logger.info("Terminate grabber...")
            self.process_grabber.terminate()

        logger.info("Get logcat dump...")
        subprocess.check_call('adb logcat -d > {}'.format(self.event_log), shell=True)

        logger.info("Upload logs...")
        subprocess.check_call(
            ["/usr/local/bin/volta-uploader", "-f", self.grab_log, "-e", self.event_log, "-t", self.core.job.task, "-s", "500"])

        if self.process_test and self.process_test.poll() is None:
            logger.info(
                "Terminating tests with PID %s", self.process_test.pid)
            self.process_test.terminate()

        return retcode

    def get_info(self):
        return AndroidInfo()


class AndroidInfo(object):
    def __init__(self):
        self.address = ''
        self.port = 80
        self.ammo_file = ''
        self.duration = 0
        self.loop_count = 1
        self.instances = 1
        self.rps_schedule = ''
