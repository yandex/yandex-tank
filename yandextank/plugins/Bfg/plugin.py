import logging
import time

import pip
from ...common.interfaces import AbstractPlugin, GeneratorPlugin

from .guns import LogGun, SqlGun, CustomGun, HttpGun, ScenarioGun, UltimateGun
from .reader import BfgReader, BfgStatsReader
from .widgets import BfgInfoWidget
from .worker import BFG
from ..Aggregator import Plugin as AggregatorPlugin
from ..Console import Plugin as ConsolePlugin
from ...stepper import StepperWrapper


class Plugin(AbstractPlugin, GeneratorPlugin):
    ''' Big Fucking Gun plugin '''
    SECTION = 'bfg'

    def __init__(self, core):
        self.log = logging.getLogger(__name__)
        AbstractPlugin.__init__(self, core)
        self.gun_type = None
        self.start_time = time.time()
        self.stepper_wrapper = StepperWrapper(self.core, Plugin.SECTION)
        self.log.info("Initialized BFG")

        self.gun_classes = {
            'log': LogGun,
            'sql': SqlGun,
            'custom': CustomGun,
            'http': HttpGun,
            'scenario': ScenarioGun,
            'ultimate': UltimateGun,
        }

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        return [
            "gun_type", "instances", "cached_stpd", "pip"
        ] + self.stepper_wrapper.get_available_options

    def configure(self):
        self.log.info("Configuring BFG...")
        self.stepper_wrapper.read_config()

    def prepare_test(self):
        pip_deps = self.get_option("pip", "").splitlines()
        self.log.info("Installing with PIP: %s", pip_deps)
        if pip_deps:
            retcode = pip.main(["install", "--user"] + pip_deps)
            if retcode != 0:
                raise RuntimeError("Could not install required deps")
            import site
            reload(site)
        self.log.info("BFG using ammo type %s", self.get_option("ammo_type"))
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
            instances=self.stepper_wrapper.instances,
            stpd_filename=self.stepper_wrapper.stpd,
            cached_stpd=cached_stpd)
        aggregator = None
        try:
            aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        except Exception as ex:
            self.log.warning("No aggregator found: %s", ex)

        if aggregator:
            aggregator.reader = BfgReader(self.bfg.results)
            aggregator.stats_reader = BfgStatsReader(
                self.bfg.instance_counter, self.stepper_wrapper.steps)

        try:
            console = self.core.get_plugin_of_type(ConsolePlugin)
        except Exception as ex:
            self.log.debug("Console not found: %s", ex)
            console = None

        if console:
            widget = BfgInfoWidget()
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
