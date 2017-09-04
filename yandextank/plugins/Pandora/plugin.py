import datetime
import json
import logging
import subprocess
import time

from ...common.interfaces import AbstractPlugin, \
    AbstractInfoWidget, GeneratorPlugin

from .reader import PandoraStatsReader
from ..Aggregator import Plugin as AggregatorPlugin
from ..Console import Plugin as ConsolePlugin
from ..Console import screen as ConsoleScreen
from ..Phantom import PhantomReader

logger = logging.getLogger(__name__)


class Plugin(AbstractPlugin, GeneratorPlugin):
    '''    Pandora load generator plugin    '''

    OPTION_CONFIG = "config"
    SECTION = "pandora"

    def __init__(self, core, cfg, cfg_updater):
        super(Plugin, self).__init__(core, cfg, cfg_updater)
        self.buffered_seconds = 2
        self.enum_ammo = False
        self.process = None
        self.process_stderr = None
        self.process_start_time = None
        self.custom_config = False
        self.sample_log = "./phout.log"
        self.expvar = True

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        opts = [
            "pandora_cmd", "buffered_seconds",
            "config_content", "config_file",
            "expvar"
        ]
        return opts

    def configure(self):
        self.expvar = self.get_option("expvar")
        self.pandora_cmd = self.get_option("pandora_cmd")
        self.buffered_seconds = self.get_option("buffered_seconds")
        with open(self.sample_log, 'w'):
            pass
        self.core.add_artifact_file(self.sample_log)

        config_content = self.get_option("config_content")
        if len(config_content) > 0:
            self.pandora_config_file = self.core.mkstemp(
                ".json", "pandora_config_")
            self.core.add_artifact_file(self.pandora_config_file)
            with open(self.pandora_config_file, 'w') as config_file:
                json.dump(config_content, config_file)
        else:
            config_file = self.get_option("config_file")
            if not config_file:
                raise RuntimeError(
                    "neither pandora config content"
                    "nor pandora config file is specified")
            else:
                extension = config_file.rsplit(".", 1)[1]
                self.pandora_config_file = self.core.mkstemp(
                    "." + extension, "pandora_config_")
                self.core.add_artifact_file(self.pandora_config_file)
                with open(config_file, 'rb') as config:
                    config_content = config.read()
                with open(self.pandora_config_file, 'wb') as config_file:
                    config_file.write(config_content)

    def prepare_test(self):
        aggregator = None
        try:
            aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        except KeyError as ex:
            logger.warning("No aggregator found: %s", ex)

        if aggregator:
            logger.info(
                "Linking sample and stats readers to aggregator. Reading samples from %s",
                self.sample_log)
            aggregator.reader = PhantomReader(self.sample_log)
            aggregator.stats_reader = PandoraStatsReader(self.expvar)

        try:
            console = self.core.get_plugin_of_type(ConsolePlugin)
        except KeyError as ex:
            logger.debug("Console not found: %s", ex)
            console = None

        if console:
            widget = PandoraInfoWidget(self)
            console.add_info_widget(widget)
            aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
            aggregator.add_result_listener(widget)

    def start_test(self):
        args = [self.pandora_cmd, "-expvar", self.pandora_config_file]
        logger.info("Starting: %s", args)
        self.process_start_time = time.time()
        process_stderr_file = self.core.mkstemp(".log", "pandora_")
        self.core.add_artifact_file(process_stderr_file)
        self.process_stderr = open(process_stderr_file, 'w')
        self.process = subprocess.Popen(
            args,
            stderr=self.process_stderr,
            stdout=self.process_stderr,
            close_fds=True)

    def is_test_finished(self):
        retcode = self.process.poll()
        if retcode is not None:
            logger.info("Subprocess done its work with exit code: %s", retcode)
            return abs(retcode)
        else:
            return -1

    def end_test(self, retcode):
        if self.process and self.process.poll() is None:
            logger.warn(
                "Terminating worker process with PID %s", self.process.pid)
            self.process.terminate()
            if self.process_stderr:
                self.process_stderr.close()
        else:
            logger.debug("Seems subprocess finished OK")
        return retcode


class PandoraInfoWidget(AbstractInfoWidget):
    ''' Right panel widget '''

    def __init__(self, pandora):
        AbstractInfoWidget.__init__(self)
        self.krutilka = ConsoleScreen.krutilka()
        self.owner = pandora
        self.reqps = 0
        self.active = 0

    def get_index(self):
        return 0

    def on_aggregated_data(self, data, stats):
        self.reqps = stats["metrics"]["reqps"]
        self.active = stats["metrics"]["instances"]

    def render(self, screen):
        text = " Pandora Test %s" % self.krutilka.next()
        space = screen.right_panel_width - len(text) - 1
        left_spaces = space / 2
        right_spaces = space / 2

        dur_seconds = int(time.time()) - int(self.owner.process_start_time)
        duration = str(datetime.timedelta(seconds=dur_seconds))

        template = screen.markup.BG_BROWN + '~' * left_spaces + \
            text + ' ' + '~' * right_spaces + screen.markup.RESET + "\n"
        template += "Command Line: %s\n"
        template += "    Duration: %s\n"
        template += "  Requests/s: %s\n"
        template += " Active reqs: %s"
        data = (self.owner.pandora_cmd, duration, self.reqps, self.active)

        return template % data
