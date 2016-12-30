import datetime
import logging
import subprocess
import time

from ...common.interfaces import AbstractPlugin, AbstractInfoWidget, GeneratorPlugin

from .config import PoolConfig, PandoraConfig, parse_schedule
from .reader import PandoraStatsReader
from ..Aggregator import Plugin as AggregatorPlugin
from ..Console import Plugin as ConsolePlugin
from ..Console import screen as ConsoleScreen
from ..Phantom import PhantomReader

logger = logging.getLogger(__name__)


class Plugin(AbstractPlugin, GeneratorPlugin):
    '''     Pandora load generator plugin    '''

    OPTION_CONFIG = "config"
    SECTION = "pandora"

    def __init__(self, core):
        super(Plugin, self).__init__(core)
        self.buffered_seconds = 2
        self.enum_ammo = False
        self.process = None
        self.process_stderr = None
        self.process_start_time = None
        self.custom_config = False

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        opts = [
            "pandora_cmd", "buffered_seconds", "ammo", "loop", "sample_log",
            "config_file", "startup_schedule", "user_schedule", "gun_type",
            "custom_config"
        ]
        return opts

    def configure(self):
        self.custom_config = self.get_option("custom_config", "0") == "1"
        self.pandora_cmd = self.get_option("pandora_cmd", "pandora")
        self.buffered_seconds = int(
            self.get_option("buffered_seconds", self.buffered_seconds))

        pool_config = PoolConfig()

        ammo = self.get_option("ammo", "")
        if ammo:
            pool_config.set_ammo(ammo)
        loop_limit = int(self.get_option("loop", "0"))
        pool_config.set_loop(loop_limit)

        self.sample_log = self.get_option("sample_log", "")
        if not self.sample_log:
            self.sample_log = self.core.mkstemp(".samples", "results_")
        self.core.add_artifact_file(self.sample_log)
        pool_config.set_sample_log(self.sample_log)

        startup_schedule = self.get_option("startup_schedule", "")
        if startup_schedule:
            pool_config.set_startup_schedule(parse_schedule(startup_schedule))
        else:
            raise RuntimeError("startup_schedule not specified")

        user_schedule = self.get_option("user_schedule", "")
        if user_schedule:
            pool_config.set_user_schedule(parse_schedule(user_schedule))
        else:
            raise RuntimeError("user_schedule not specified")

        shared_schedule = bool(int(self.get_option("shared_schedule", "1")))
        pool_config.set_shared_schedule(shared_schedule)

        target = self.get_option("target", "localhost:3000")
        pool_config.set_target(target)

        gun_type = self.get_option("gun_type", "http")
        if gun_type == 'https':
            pool_config.set_ssl(True)
            logger.info("SSL is on")
            gun_type = "http"
        logger.info("Pandora gun type is: %s", gun_type)
        pool_config.set_gun_type(gun_type)

        ammo_type = self.get_option("ammo_type", "jsonline/http")
        logger.info("Pandora ammo type is: %s", ammo_type)
        pool_config.set_ammo_type(ammo_type)

        self.pandora_config = PandoraConfig()
        self.pandora_config.add_pool(pool_config)

        self.pandora_config_file = self.get_option("config_file", "")
        if not self.pandora_config_file:
            if self.custom_config:
                raise RuntimeError(
                    "You said you would like to use custom config,"
                    " but you didn't specify it")
            self.pandora_config_file = self.core.mkstemp(
                ".json", "pandora_config_")
        self.core.add_artifact_file(self.pandora_config_file)
        if not self.custom_config:
            with open(self.pandora_config_file, 'w') as config_file:
                config_file.write(self.pandora_config.json())

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
            aggregator.stats_reader = PandoraStatsReader()

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
