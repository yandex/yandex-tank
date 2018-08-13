import datetime
import logging
import subprocess
import time
import yaml

from netort.resource import manager as resource_manager

from .reader import PandoraStatsReader
from ..Console import Plugin as ConsolePlugin
from ..Console import screen as ConsoleScreen
from ..Phantom import PhantomReader
from ...common.interfaces import AbstractInfoWidget, GeneratorPlugin

logger = logging.getLogger(__name__)


class Plugin(GeneratorPlugin):
    """    Pandora load generator plugin    """

    OPTION_CONFIG = "config"
    SECTION = "pandora"
    DEFAULT_REPORT_FILE = "phout.log"

    def __init__(self, core, cfg):
        super(Plugin, self).__init__(core, cfg)
        self.enum_ammo = False
        self.process_start_time = None
        self.pandora_cmd = None
        self.pandora_config_file = None
        self.config_contents = None
        self.custom_config = False
        self.expvar = True
        self.sample_log = None

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
        self.affinity = self.get_option("affinity", "")

        # get config_contents and patch it: expand resources via resource manager
        # config_content option has more priority over config_file
        if self.get_option("config_content"):
            logger.info('Found config_content option configuration')
            self.config_contents = self.__patch_and_dump_config(self.get_option("config_content"))
        elif self.get_option("config_file"):
            logger.info('Found config_file option configuration')
            with open(self.get_option("config_file"), 'rb') as config:
                raw_config_contents = yaml.safe_load(config.read())
            self.config_contents = self.__patch_and_dump_config(raw_config_contents)
        else:
            raise RuntimeError("Neither pandora.config_content, nor pandora.config_file specified")
        logger.debug('Config after parsing for patching: %s', self.config_contents)
        self.sample_log = self.__find_closest_report_file()
        with open(self.sample_log, 'w'):
            pass
        self.core.add_artifact_file(self.sample_log)

    def __patch_and_dump_config(self, cfg_dict):
        config_content = self.patch_config(cfg_dict)
        self.pandora_config_file = self.core.mkstemp(".yaml", "pandora_config_")
        self.core.add_artifact_file(self.pandora_config_file)
        with open(self.pandora_config_file, 'w') as config_file:
            yaml.dump(config_content, config_file)
        return config_content

    def __find_closest_report_file(self):
        for pool in self.config_contents['pools']:
            if pool.get('result'):
                if pool.get('result').get('destination'):
                    report_filename = pool.get('result').get('destination')
                    logger.info('Found report file in pandora config: %s', report_filename)
                    return report_filename
        return self.DEFAULT_REPORT_FILE

    def get_reader(self):
        if self.reader is None:
            self.reader = PhantomReader(self.sample_log)
        return self.reader

    def get_stats_reader(self):
        if self.stats_reader is None:
            self.stats_reader = PandoraStatsReader(self.expvar)
        return self.stats_reader

    def prepare_test(self):
        try:
            console = self.core.get_plugin_of_type(ConsolePlugin)
        except KeyError as ex:
            logger.debug("Console not found: %s", ex)
            console = None

        if console:
            widget = PandoraInfoWidget(self)
            console.add_info_widget(widget)
            self.core.job.aggregator.add_result_listener(widget)

    def start_test(self):
        args = [self.pandora_cmd, "-expvar", self.pandora_config_file]
        if self.affinity:
            self.core.__setup_affinity(self.affinity, args=args)
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

    @staticmethod
    def patch_config(config):
        """
        download remote resources, replace links with local filenames
        :param dict config: pandora config
        """
        for pool in config['pools']:
            if 'file' in pool.get('ammo', {}):
                pool['ammo']['file'] = resource_manager.resource_filename(pool['ammo']['file'])
        return config


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
