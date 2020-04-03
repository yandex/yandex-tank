import logging
import time
from threading import Event
import subprocess

import yaml

from .reader import BfgStatsReader
from .widgets import BfgInfoWidget
from ..Phantom import PhantomReader, string_to_df
from ..Console import Plugin as ConsolePlugin
from ...common.interfaces import GeneratorPlugin
from ...common.util import FileMultiReader, tail_lines
from ...stepper import StepperWrapper


class Plugin(GeneratorPlugin):
    """ internal Big Fucking Gun plugin """
    SECTION = 'bfg'

    def __init__(self, core, cfg, name):
        super(Plugin, self).__init__(core, cfg, name)
        self.close_event = Event()
        self._bfg = None
        self.bfg_cmd = self.get_option("bfg_cmd")
        self.bfg_config_file = None
        self.log = logging.getLogger(__name__)
        self.gun_type = None
        self.stepper_wrapper = StepperWrapper(core, cfg)
        self.log.info("Initialized BFG")
        self.report_filename = "phout.log"
        self.results_listener = None

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        return [
            "gun_type", "instances", "cached_stpd", "pip"
        ]

    def configure(self):
        self.__dump_config()
        self.core.add_artifact_file(self.report_filename)
        with open(self.report_filename, "a"):
            self.log.debug("Bfg2020 phout file created")

    def __dump_config(self):
        config_content = self.core.config.validated["bfg"]
        cache_dir = self.get_option("cache_dir") or self.core.artifacts_base_dir
        config_content["cache_dir"] = cache_dir
        self.bfg_config_file = self.core.mkstemp(".yaml", "bfg_config_")
        self.core.add_artifact_file(self.bfg_config_file)
        with open(self.bfg_config_file, 'w') as config_file:
            yaml.dump(config_content, config_file)

    def get_reader(self, parser=string_to_df):
        if self.reader is None:
            self.reader = FileMultiReader(self.report_filename, self.close_event)
        return PhantomReader(self.reader.get_file(), parser=parser)

    def get_stats_reader(self):
        if self.stats_reader is None:
            self.stats_reader = BfgStatsReader("1234")
        return self.stats_reader

    def prepare_test(self):
        try:
            console = self.core.get_plugin_of_type(ConsolePlugin)
        except Exception as ex:
            self.log.debug("Console not found: %s", ex)
            console = None

        if console:
            widget = BfgInfoWidget()
            console.add_info_widget(widget)
            self.core.job.aggregator.add_result_listener(widget)

    def start_test(self):
        args = [self.bfg_cmd] +\
            ['--config='+self.bfg_config_file]
        self.log.info("Starting: %s", args)
        self.start_time = time.time()
        self.process_stderr_file = self.core.mkstemp(".log", "bfg_")
        self.core.add_artifact_file(self.process_stderr_file)
        self.process_stderr = open(self.process_stderr_file, 'w')
        try:
            self.process = subprocess.Popen(
                args,
                stderr=self.process_stderr,
                stdout=self.process_stderr,
                close_fds=True)
        except OSError:
            self.log.debug(
                "Unable to start Bfg binary. Args: %s", args, exc_info=True)
            raise RuntimeError(
                "Unable to start Bfg binary and/or file does not exist: %s" % args)

    def is_test_finished(self):
        retcode = self.process.poll()
        if retcode is not None and retcode == 0:
            self.log.info("BFG subprocess done its work successfully and finished w/ retcode 0")
            self.close_event.set()
            return retcode
        elif retcode is not None and retcode != 0:
            lines_amount = 20
            self.log.info("BFG finished with non-zero retcode. Last %s logs of BFG log:", lines_amount)
            self.close_event.set()
            last_log_contents = tail_lines(self.process_stderr_file, lines_amount)
            for logline in last_log_contents:
                self.log.info(logline.strip('\n'))
            return abs(retcode)
        else:
            return -1

    def end_test(self, retcode):
        if self.process and self.process.poll() is None:
            self.log.warning(
                "Terminating worker process with PID %s", self.process.pid)
            self.process.terminate()
            if self.process_stderr:
                self.process_stderr.close()
        else:
            self.log.debug("Subprocess finished")
        self.close_event.set()
        return retcode
