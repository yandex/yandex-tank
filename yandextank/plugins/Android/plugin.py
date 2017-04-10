import logging
import subprocess
import time
import urllib
import sys
import glob
import os
from multiprocessing import Process
from signal import SIGKILL

try:
    from volta.analysis import grab, uploader
except Exception:
    raise RuntimeError("Please install volta. https://github.com/yandex-load/volta")

from pkg_resources import resource_filename
from ...common.interfaces import AbstractPlugin, GeneratorPlugin
from .reader import AndroidReader, AndroidStatsReader

logger = logging.getLogger(__name__)


class Plugin(AbstractPlugin, GeneratorPlugin):
    SECTION = "android"
    SECTION_META = "meta"

    def __init__(self, core):
        super(Plugin, self).__init__(core)
        self.apk_path = None
        self.test_path = None
        self.package = None
        self.package_test = None
        self.clazz = None
        self.device = None
        self.test_runner = None
        self.process_test = None
        self.process_stderr = None
        self.process_grabber = None
        self.apk = "./app.apk"
        self.test = "./app-test.apk"
        self.grab_log = "./output.bin"
        self.event_log = "./events.log"

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        opts = ["package", "test_package", "apk", "test_apk", "class", "test_runner"]
        return opts

    def configure(self):
        # plugin part
        self.apk_path = self.get_option("apk")
        self.test_path = self.get_option("test_apk")
        self.clazz = self.get_option("class")
        self.package = self.get_option("package")
        self.package_test = self.get_option("test_package")
        self.test_runner = self.get_option("test_runner")

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
            logger.info('Your OS is not supported yet')

        logger.info("Ports = " + ''.join(ports))
        try:
            self.device = [port for port in ports if 'Bluetooth' not in port][0]
            logger.info("Found device = " + self.device)
        except Exception:
            logger.info("Device not found")

        logger.info("Download apk...")
        urllib.urlretrieve(self.apk_path, self.apk)

        logger.info("Download test...")
        urllib.urlretrieve(self.test_path, self.test)

        logger.info("Uninstall the lightning...")
        subprocess.check_output(["adb", "uninstall", "net.yandex.overload.lightning"])

        logger.info("Uninstall the app...")
        subprocess.check_output(["adb", "uninstall", self.package])

        logger.info("Uninstall the test...")
        subprocess.check_output(["adb", "uninstall", self.package_test])

        lightning = resource_filename(__name__, 'binary/lightning.apk')
        logger.info("Get from resources " + lightning)

        logger.info("Install the lightning...")
        subprocess.check_output(["adb", "install", lightning])

        logger.info("Install the apk...")
        subprocess.check_output(["adb", "install", self.apk])

        logger.info("Install the test...")
        subprocess.check_output(["adb", "install", self.test])

        logger.info("Clear logcat...")
        subprocess.check_output(["adb", "logcat", "-c"])

    def start_test(self):
        if self.device:
            logger.info("Start grabber...")
            args = {
                'device': self.device,
                'seconds': 10800,
                'output': self.grab_log,
                'debug': False,
                'binary': False
            }
            self.process_grabber = Process(target=grab.main, args=(args,))
            self.process_grabber.start()

        process_stderr_file = self.core.mkstemp(".log", "android_")
        self.core.add_artifact_file(process_stderr_file)
        self.process_stderr = open(process_stderr_file, 'w')

        logger.info("Start flashlight...")
        args = ["adb", "shell", "am", "start", "-n",
                "net.yandex.overload.lightning/net.yandex.overload.lightning.MainActivity"]
        subprocess.Popen(args)
        time.sleep(12)

        args = ["adb", "shell", "am", "instrument", "-w", "-e", "class", self.clazz,
                '{package}/{runner}'.format(package=self.package_test, runner=self.test_runner)]
        logger.info("Starting: %s", args)
        self.process_test = subprocess.Popen(
            args,
            stderr=self.process_stderr,
            stdout=self.process_stderr,
            close_fds=True
        )

    def is_test_finished(self):
        retcode = self.process_test.poll()
        if retcode is not None:
            logger.info("Subprocess done its work with exit code: %s", retcode)
            return abs(retcode)
        else:
            return -1

    def end_test(self, retcode):
        if self.process_grabber:
            logger.info("Kill grabber...")
            os.kill(self.process_grabber.pid, SIGKILL)

        logger.info("Get logcat dump...")
        subprocess.check_call('adb logcat -d > {file}'.format(file=self.event_log), shell=True)

        if os.path.exists(self.grab_log):
            logger.info("Upload logs...")
            args = {
                'filename': self.grab_log,
                'events': self.event_log,
                'samplerate': 500,
                'slope': 1,
                'offset': 0,
                'bynary': False,
                'job_config': {
                    'task': self.core.get_option(self.SECTION_META, 'task').decode('utf8'),
                    'jobname': self.core.get_option(self.SECTION_META, 'job_name').decode('utf8'),
                    'dsc': self.core.get_option(self.SECTION_META, 'job_dsc').decode('utf8'),
                    'component': self.core.get_option('meta', 'component')
                }
            }
            process_uploader = Process(target=uploader.main, args=(args,))
            process_uploader.start()
            process_uploader.join()

        if self.process_test and self.process_test.poll() is None:
            logger.info("Terminating tests with PID %s", self.process_test.pid)
            self.process_test.terminate()
            if self.process_stderr:
                self.process_stderr.close()

        logger.info("Uninstall the app...")
        subprocess.check_output(["adb", "uninstall", self.package])

        logger.info("Uninstall the test...")
        subprocess.check_output(["adb", "uninstall", self.package_test])

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
