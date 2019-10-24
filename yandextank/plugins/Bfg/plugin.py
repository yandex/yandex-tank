import logging
import time
from threading import Event, Thread

import pip

from .guns import LogGun, SqlGun, CustomGun, HttpGun, ScenarioGun, UltimateGun
from .reader import BfgReader, BfgStatsReader
from .widgets import BfgInfoWidget
from ..Phantom import PhantomReader, string_to_df
from .worker import BFGMultiprocessing, BFGGreen
from ..Console import Plugin as ConsolePlugin
from ...common.interfaces import GeneratorPlugin
from ...common.util import FileMultiReader
from ...stepper import StepperWrapper


class Plugin(GeneratorPlugin):
    """ Big Fucking Gun plugin """
    SECTION = 'bfg'

    def __init__(self, core, cfg, name):
        super(Plugin, self).__init__(core, cfg, name)
        self.close_event = Event()
        self._bfg = None
        self.log = logging.getLogger(__name__)
        self.gun_type = None
        self.stepper_wrapper = StepperWrapper(core, cfg)
        self.log.info("Initialized BFG")
        self.report_filename = "bfgout.log"
        self.results_listener = None

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
        with open(self.report_filename, 'w'):
            pass
        self.core.add_artifact_file(self.report_filename)

    def _write_results_into_file(self):
        """listens for messages on the q, writes to file. """
        reader = BfgReader(self.bfg.results, self.close_event)
        columns = ['receive_ts', 'tag', 'interval_real', 'connect_time', 'send_time', 'latency', 'receive_time',
                   'interval_event', 'size_out', 'size_in', 'net_code', 'proto_code']
        for entry in reader:
            if entry is not None:
                entry.receive_ts = entry.receive_ts.round(3)
                with open(self.report_filename, 'a') as report_file:
                    report_file.write(entry.to_csv(index=False, header=False, sep='\t', columns=columns))
            time.sleep(0.1)

    def get_reader(self, parser=string_to_df):
        if self.reader is None:
            self.reader = FileMultiReader(self.report_filename, self.close_event)
        return PhantomReader(self.reader.get_file(), parser=parser)

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
            from importlib import reload
            reload(site)
        self.log.info("BFG using ammo type %s", self.get_option("ammo_type"))
        gun_type = self.get_option("gun_type")
        if gun_type in self.gun_classes:
            self.gun = self.gun_classes[gun_type](self.core, self.get_option('gun_config'))
        else:
            raise NotImplementedError(
                'No such gun type implemented: "%s"' % gun_type)

        self.results_listener = Thread(target=self._write_results_into_file, name="ResultsQueueListener")

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
        if self.results_listener is not None:
            self.results_listener.start()
        else:
            self.log.fatal("Result listener is not initialized")

    def is_test_finished(self):
        if self.bfg.running():
            return -1
        else:
            self.log.info("BFG finished")
            self.close_event.set()
            self.stats_reader.close()
            return 0

    def end_test(self, retcode):
        if self.bfg.running():
            self.log.info("Terminating BFG")
            self.bfg.stop()
        self.close_event.set()
        self.stats_reader.close()
        return retcode
