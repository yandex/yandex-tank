''' Generic native load generator '''
from Tank.Plugins.Aggregator import AggregatorPlugin
from Tank.Plugins.ConsoleOnline import ConsoleOnlinePlugin
from tankcore import AbstractPlugin
from Queue import Queue
import logging
import time
from threading import Timer
from Tank.stepper import StepperWrapper, StpdReader


class BFGPlugin(AbstractPlugin):

    ''' JMeter tank plugin '''
    SECTION = 'bfg'

    def __init__(self, core):
        self.log = logging.getLogger(__name__)
        AbstractPlugin.__init__(self, core)
        self.gun_type = None
        self.start_time = time.time()
        self.stepper_wrapper = StepperWrapper(self.core, BFGPlugin.SECTION)
        self.log.info("Initialized BFG")

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        return ["gun_type", "instances"] + self.stepper_wrapper.get_available_options

    def configure(self):
        self.log.info("Configuring BFG...")
        self.stepper_wrapper.read_config()

    def prepare_test(self):
        self.stepper_wrapper.prepare_stepper()
        self.bfg = BFG(
            gun_type=self.get_option("gun_type"),
            instances=self.get_option("instances", '15'),
            stpd_filename=self.stepper_wrapper.stpd,
        )
        aggregator = None
        try:
            aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        except Exception, ex:
            self.log.warning("No aggregator found: %s", ex)

        if aggregator:
            # TODO: create aggregator reader
            # aggregator.reader =
            pass

        try:
            console = self.core.get_plugin_of_type(ConsoleOnlinePlugin)
        except Exception, ex:
            self.log.debug("Console not found: %s", ex)
            console = None

        if console:
            # TODO: make a widget here
            # widget = BFGInfoWidget(self)
            # console.add_info_widget(widget)
            # if aggregator:
            #     aggregator.add_result_listener(widget)
            pass
        self.log.info("Prepared BFG")

    def start_test(self):
        self.log.info("Starting BFG")
        # TODO: start BFG here
        self.start_time = time.time()
        self.bfg.start()

    def is_test_finished(self):
        if self.bfg.running:
            return -1
        else:
            retcode = self.bfg.retcode
            self.log.info(
                "BFG finished with exit code: %s", retcode)
            return retcode

    def end_test(self, retcode):
        if self.bfg.running:
            self.log.info("Terminating BFG")
            self.bfg.stop()
        return retcode


class BFG(object):

    def __init__(
        self,
        gun_type,
        instances,
        stpd_filename,
    ):
        self.log = logging.getLogger(__name__)
        self.log.info(
            "BFG using gun '%s', stpd from %s", gun_type, stpd_filename)
        self.gun_type = gun_type
        self.stpd_filename = stpd_filename
        self.instances = int(instances)
        self.running = False
        self.retcode = None
        self.ammo_cache = Queue(self.instances)

    def start(self):
        self.running = True
        start_time = time.time()
        stpd = StpdReader(self.stpd_filename)
        tasks = []
        for timestamp, missile, marker in stpd:
            delay = timestamp / 1000.0 - (time.time() - start_time)
            timer_task = Timer(delay, self._shoot, [missile, marker])
            timer_task.start()
            tasks.append(timer_task)
        [task.join() for task in tasks]
        self.stop()

    def _shoot(self, missile, marker):
        self.log.info("Executing on timer, %s", time.time())
        self.log.info("Missile: %s\n%s", marker, missile)

    def stop(self):
        self.running = False
        self.retcode = 0
