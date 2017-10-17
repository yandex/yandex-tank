import logging
import time

import pip
from ...common.interfaces import AbstractPlugin, GeneratorPlugin

from .reader import BfgReader, BfgStatsReader
from .widgets import BfgInfoWidget
from ..Aggregator import Plugin as AggregatorPlugin
from ..Console import Plugin as ConsolePlugin


class Plugin(AbstractPlugin, GeneratorPlugin):
    ''' Big Fucking Gun plugin '''
    SECTION = 'bfg9000'

    def __init__(self, core, cfg, cfg_updater):
        self.log = logging.getLogger(__name__)
        AbstractPlugin.__init__(self, core, cfg, cfg_updater)
        self.start_time = time.time()
        # TODO: check python3 exists
        # TODO: add python3 path option
        # TODO: add pip3 path option
        # TODO: add BFG9000 config option (dict)
        self.log.info("Initialized BFG9000")

    @staticmethod
    def get_key():
        return __file__

    def prepare_test(self):
        # TODO: change to external pip3 call
        pip_deps = self.get_option("pip", "").splitlines()
        self.log.info("Installing with PIP: %s", pip_deps)
        if pip_deps:
            retcode = pip.main(["install", "--user"] + pip_deps)
            if retcode != 0:
                raise RuntimeError("Could not install required deps")
            import site
            reload(site)

        # TODO: create files for BFG phout and pass it to reader
        # TODO: show BfgStatsReader where to get BFG stats (maybe http handle)

        # if aggregator:
        #     aggregator.reader = BfgReader(self.bfg.results)
        #     aggregator.stats_reader = BfgStatsReader(
        #         self.bfg.instance_counter, self.stepper_wrapper.steps)

        try:
            console = self.core.get_plugin_of_type(ConsolePlugin)
        except Exception as ex:
            self.log.debug("Console not found: %s", ex)
            console = None

        # TODO: adapt this for BFG
        if console:
            widget = BfgInfoWidget()
            console.add_info_widget(widget)
            if aggregator:
                aggregator.add_result_listener(widget)
        self.log.info("Prepared BFG9000")

    def start_test(self):
        self.log.info("Starting BFG9000")
        self.start_time = time.time()
        # TODO: start external BFG process (see phantom and shootexec)

    def is_test_finished(self):
        # TODO: add correct check (see phantom and shootexec)
        # if self.bfg.running():
        #     return -1
        # else:
        #     self.log.info("BFG finished")
        #     return 0
        return -1

    def end_test(self, retcode):
        # TODO: add correct process termination (see phantom and shootexec)
        return retcode
