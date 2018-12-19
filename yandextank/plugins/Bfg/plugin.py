import logging
import time

import pip

from .guns import LogGun, SqlGun, CustomGun, HttpGun, ScenarioGun, UltimateGun
from .reader import BfgReader, BfgStatsReader
from .widgets import BfgInfoWidget
from .worker import BFGMultiprocessing, BFGGreen
from ..Console import Plugin as ConsolePlugin
from ...common.interfaces import GeneratorPlugin
from ...stepper import StepperWrapper


class Plugin(GeneratorPlugin):
    """ Big Fucking Gun plugin """
    SECTION = 'bfg'

    def __init__(self, core, cfg, name):
        super(Plugin, self).__init__(core, cfg, name)
        self._bfg = None
        self.log = logging.getLogger(__name__)
        self.gun_type = None
        self.start_time = time.time()
        self.stepper_wrapper = StepperWrapper(core, cfg)
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
        ]

    def configure(self):
        self.log.info("Configuring BFG...")
        self.stepper_wrapper.read_config()
        self.stepper_wrapper.prepare_stepper()

    def get_reader(self):
        if self.reader is None:
            self.reader = BfgReader(self.bfg.results)
        return self.reader

    def get_stats_reader(self):
        if self.stats_reader is None:
            self.stats_reader = BfgStatsReader(self.bfg.instance_counter, self.stepper_wrapper.steps)
        return self.stats_reader

    @property
    def bfg(self):
        if self._bfg is None:
            BFG = BFGGreen if self.get_option("worker_type", "") == "green" else BFGMultiprocessing
            self._bfg = BFG(
                gun=self.gun,
                instances=self.stepper_wrapper.instances,
                stpd_filename=self.stepper_wrapper.stpd,
                cached_stpd=self.get_option("cached_stpd"),
                green_threads_per_instance=int(self.get_option('green_threads_per_instance', 1000)),
            )
        return self._bfg

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
        gun_type = self.get_option("gun_type")
        if gun_type in self.gun_classes:
            self.gun = self.gun_classes[gun_type](self.core, self.get_option('gun_config'))
        else:
            raise NotImplementedError(
                'No such gun type implemented: "%s"' % gun_type)

        try:
            console = self.core.get_plugin_of_type(ConsolePlugin)
        except Exception as ex:
            self.log.debug("Console not found: %s", ex)
            console = None

        if console:
            widget = BfgInfoWidget()
            console.add_info_widget(widget)
            self.core.job.aggregator.add_result_listener(widget)
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
