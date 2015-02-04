from yandextank.core import AbstractPlugin
from yandextank.plugins.Aggregator import AggregatorPlugin
from yandextank.plugins.ConsoleOnline import ConsoleOnlinePlugin
import logging
import time
from yandextank.stepper import StepperWrapper
from guns import LogGun, SqlGun, CustomGun, HttpGun
from widgets import BFGInfoWidget
from worker import BFG
from reader import BFGReader


class BFGPlugin(AbstractPlugin):

    ''' Big Fucking Gun plugin '''
    SECTION = 'bfg'

    def __init__(self, core):
        self.log = logging.getLogger(__name__)
        AbstractPlugin.__init__(self, core)
        self.gun_type = None
        self.start_time = time.time()
        self.stepper_wrapper = StepperWrapper(self.core, BFGPlugin.SECTION)
        self.log.info("Initialized BFG")

        self.gun_classes = {
            'log': LogGun,
            'sql': SqlGun,
            'custom': CustomGun,
            'http': HttpGun,
        }

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        return ["gun_type", "instances", "cached_stpd"] + self.stepper_wrapper.get_available_options

    def configure(self):
        self.log.info("Configuring BFG...")
        self.stepper_wrapper.read_config()

    def prepare_test(self):
        self.log.info(self.get_option("ammo_type"))
        self.stepper_wrapper.prepare_stepper()
        gun_type = self.get_option("gun_type")
        if gun_type in self.gun_classes:
            self.gun = self.gun_classes[gun_type](self.core)
        else:
            raise NotImplementedError(
                'No such gun type implemented: "%s"' % gun_type)
        cached_stpd_option = self.get_option("cached_stpd", '0')
        if cached_stpd_option == '1':
            cached_stpd = True
        else:
            cached_stpd = False
        self.bfg = BFG(
            gun=self.gun,
            instances=self.get_option("instances", '15'),
            threads=self.get_option("threads", '10'),
            stpd_filename=self.stepper_wrapper.stpd,
            cached_stpd=cached_stpd,
            zmq=self.get_option("zmq", None)
        )
        aggregator = None
        try:
            aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        except Exception, ex:
            self.log.warning("No aggregator found: %s", ex)

        if aggregator:
            result_cache_size = int(self.get_option("result_cache_size", '5'))
            aggregator.reader = BFGReader(
                aggregator, self.bfg, result_cache_size=result_cache_size)

        try:
            console = self.core.get_plugin_of_type(ConsoleOnlinePlugin)
        except Exception, ex:
            self.log.debug("Console not found: %s", ex)
            console = None

        if console:
            widget = BFGInfoWidget()
            console.add_info_widget(widget)
            if aggregator:
                aggregator.add_result_listener(widget)
        self.log.info("Prepared BFG")

    def start_test(self):
        self.log.info("Starting BFG")
        self.start_time = time.time()
        self.bfg.start()

    def is_test_finished(self):
        if self.bfg.running():
            return -1
        else:
            self.log.info("BFG finished")
            return 0

    def end_test(self, retcode):
        if self.bfg.running():
            self.log.info("Terminating BFG")
            self.bfg.stop()
        return retcode
