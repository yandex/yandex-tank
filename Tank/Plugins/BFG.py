''' Generic native load generator '''
from Tank.Plugins.Aggregator import AggregatorPlugin
from Tank.Plugins.ConsoleOnline import ConsoleOnlinePlugin
from tankcore import AbstractPlugin
import logging
import time
from Tank.stepper import Stepper


class BFGPlugin(AbstractPlugin):

    ''' JMeter tank plugin '''
    SECTION = 'bfg'

    def __init__(self, core):
        self.log = logging.getLogger(__name__)
        AbstractPlugin.__init__(self, core)
        self.gun_type = None
        self.start_time = time.time()
        self.log.info("Initialized BFG")

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        return ["gun_type", "rps_schedule", "ammo_limit", "loop_limit", "instances", "ammo_file"]

    def configure(self):
        # TODO: move this elsewhere
        def make_steps(schedule):
            steps = []
            for step in " ".join(schedule.split("\n")).split(')'):
                if step.strip():
                    steps.append(step.strip() + ')')
            return steps
        self.conf = {
            'gun_type': self.get_option("gun_type"),
            'rps_schedule': make_steps(self.get_option("rps_schedule")),
            'ammo_limit': self.get_option("ammo_limit", '-1'),
            'loop_limit': self.get_option("loop_limit", '-1'),
            'instances': self.get_option("instances", '15'),
            'ammo_file': self.get_option("ammo_file", 'ammo'),
        }
        self.bfg = BFG(**self.conf)
        self.log.info("Configured BFG")


    def prepare_test(self):
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
        rps_schedule,
        ammo_limit,
        loop_limit,
        instances,
        ammo_file,
    ):
        self.gun_type = gun_type
        self.instances = int(instances)
        self.stepper = Stepper(
            rps_schedule=rps_schedule,
            ammo_file=ammo_file,
            loop_limit=loop_limit,
            ammo_limit=ammo_limit,
            ammo_type = gun_type,
        )
        self.running = False
        self.retcode = None

    def start(self):
        self.running = True

    def stop(self):
        self.running = False
        self.retcode = 0
