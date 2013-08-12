''' Generic native load generator '''
from Tank.Plugins.Aggregator import AggregatorPlugin
from Tank.Plugins.ConsoleOnline import ConsoleOnlinePlugin
from tankcore import AbstractPlugin
import time


class BFGPlugin(AbstractPlugin):

    ''' JMeter tank plugin '''
    SECTION = 'bfg'

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.gun_type = None
        self.start_time = time.time()

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        return ["gun_type", "load", "ammo_limit", "loop_limit", "instances"]

    def configure(self):
        self.gun_type = self.get_option("gun_type")
        self.load = self.get_option("load")
        self.ammo_limit = self.get_option("ammo_limit")
        self.loop_limit = self.get_option("loop_limit")
        self.instances = self.get_option("instances")

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

    def start_test(self):
        self.log.info("Starting BFG")
        # TODO: start BFG here
        self.start_time = time.time()
        # self.bfg = ...

    def is_test_finished(self):
        retcode = -1 # check if test is finished
        if retcode != None:
            self.log.info(
                "BFG finished with exit code: %s", retcode)
            return retcode
        else:
            return -1

    def end_test(self, retcode):
        if self.bfg.running():
            self.log.info("Terminating BFG")
            self.bfg.stop()
        return retcode
