import datetime
import logging
import subprocess
import time
import os
from threading import Event

import yaml
import json
import pprint

from netort.resource import manager as resource_manager
from netort.resource import HttpOpener

from .reader import PandoraStatsReader
from ..Console import Plugin as ConsolePlugin
from ..Console import screen as ConsoleScreen
from ...common.interfaces import AbstractInfoWidget, GeneratorPlugin
from ...common.util import tail_lines, FileMultiReader, FileLinesBackwardsIterator, PhantomReader, string_to_df

logger = logging.getLogger(__name__)


class Plugin(GeneratorPlugin):
    """    Pandora load generator plugin    """

    OPTION_CONFIG = "config"
    SECTION = "pandora"
    DEFAULT_REPORT_FILE = "phout.log"
    DEFAULT_EXPVAR_PORT = 1234

    def __init__(self, core, cfg, name):
        super(Plugin, self).__init__(core, cfg, name)
        self.output_finished = Event()
        self.enum_ammo = False
        self.process_start_time = None
        self.pandora_cmd = None
        self.pandora_config_file = None
        self.config_contents = None
        self.custom_config = False
        self.expvar = None
        self.expvar_port = None
        self.sample_log = None
        self.__address = None
        self.__schedule = None
        self.ammofile = None
        self.process_stderr_file = None

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        opts = [
            "pandora_cmd", "buffered_seconds",
            "config_content", "config_file"
        ]
        return opts

    def configure(self):
        pandora_path = self.get_option("pandora_cmd").strip()
        if pandora_path.startswith("http://") or pandora_path.startswith("https://"):
            self.pandora_cmd = resource_manager.resource_filename(pandora_path)
            os.chmod(self.pandora_cmd, 0o755)
        else:
            self.pandora_cmd = pandora_path
        self.buffered_seconds = self.get_option("buffered_seconds")
        self.affinity = self.get_option("affinity", "")

        # get config_contents and patch it: expand resources via resource manager
        # config_content option has more priority over config_file
        if self.get_option("config_content"):
            logger.info('Found config_content option configuration')
            self.config_contents = self.__patch_raw_config_and_dump(self.get_option("config_content"))
        elif self.get_option("config_file"):
            logger.info('Found config_file option configuration')
            with open(self.get_option("config_file"), 'rb') as config:
                external_file_config_contents = yaml.load(config.read())
            self.config_contents = self.__patch_raw_config_and_dump(external_file_config_contents)
        else:
            raise RuntimeError("Neither pandora.config_content, nor pandora.config_file specified")
        logger.error('Config after parsing for patching: %s', self.config_contents)

        # find report filename and add to artifacts
        self.sample_log = self.__find_report_filename()
        with open(self.sample_log, 'w'):
            pass
        self.core.add_artifact_file(self.sample_log)

    def __patch_raw_config_and_dump(self, cfg_dict):
        if not cfg_dict:
            raise RuntimeError('Empty pandora config')
        # patch
        config_content = self.patch_config(cfg_dict)
        # dump
        self.pandora_config_file = self.core.mkstemp(".yaml", "pandora_config_")
        self.core.add_artifact_file(self.pandora_config_file)
        with open(self.pandora_config_file, 'w') as config_file:
            yaml.dump(config_content, config_file)
        return config_content

    def patch_config(self, config):
        """
        download remote resources, replace links with local filenames
        add result file section
        :param dict config: pandora config
        """
        # get expvar parameters
        if config.get("monitoring"):
            if config["monitoring"].get("expvar"):
                self.expvar = config["monitoring"]["expvar"].get("enabled")
                if config["monitoring"]["expvar"].get("port"):
                    self.expvar_port = config["monitoring"]["expvar"].get("port")
                else:
                    self.expvar_port = self.DEFAULT_EXPVAR_PORT
        # or set if expvar not exists
        else:
            config["monitoring"] = {
                "expvar": {
                    "enabled": True,
                }
            }
            self.expvar = True
            self.expvar_port = self.DEFAULT_EXPVAR_PORT

        # FIXME refactor pandora plx
        for pool in config['pools']:
            if pool.get('ammo', {}).get('file', ''):
                self.ammofile = pool['ammo']['file']
                opener = resource_manager.get_opener(self.ammofile)
                if isinstance(opener, HttpOpener):
                    pool['ammo']['file'] = opener.download_file(True, try_ungzip=True)
                else:
                    pool['ammo']['file'] = opener.get_filename

            if pool.get('ammo', {}).get('source', {}).get('path', ''):
                self.ammofile = pool['ammo']['source']['path']
                opener = resource_manager.get_opener(self.ammofile)
                if isinstance(opener, HttpOpener):
                    pool['ammo']['source']['path'] = opener.download_file(True, try_ungzip=True)
                else:
                    pool['ammo']['source']['path'] = opener.get_filename

            if not pool.get('result') or 'phout' not in pool.get('result', {}).get('type', ''):
                logger.warning('Seems like pandora result file not specified... adding defaults')
                pool['result'] = dict(
                    destination=self.DEFAULT_REPORT_FILE,
                    type='phout',
                )
        return config

    @property
    def address(self):
        if not self.__address:
            for pool in self.config_contents['pools']:
                if pool.get('gun', {}).get('target'):
                    self.__address = pool.get('gun', {}).get('target').strip()
                    break
            else:
                self.__address = 'unknown'
        return self.__address

    @property
    def schedule(self):
        if not self.__schedule:
            for pool in self.config_contents['pools']:
                if pool.get('rps'):
                    self.__schedule = pool.get('rps')
                    break
            else:
                self.__schedule = 'unknown'
        return self.__schedule

    def get_info(self):
        return self.Info(
            address=self.address,
            ammo_file=self.ammofile,
            duration=0,
            instances=0,
            loop_count=0,
            port=self.address.split(':')[-1],
            rps_schedule=self.schedule
        )

    def __find_report_filename(self):
        for pool in self.config_contents['pools']:
            if pool.get('result', {}).get('destination', None):
                report_filename = pool.get('result').get('destination')
                logger.info('Found report file in pandora config: %s', report_filename)
                return report_filename
        return self.DEFAULT_REPORT_FILE

    def get_reader(self, parser=string_to_df):
        if self.reader is None:
            self.reader = FileMultiReader(self.sample_log, self.output_finished)
        return PhantomReader(self.reader.get_file(), parser=parser)

    def get_stats_reader(self):
        if self.stats_reader is None:
            self.stats_reader = PandoraStatsReader(self.expvar, self.expvar_port)
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
        args = [self.pandora_cmd, self.pandora_config_file]
        if self.affinity:
            self.core.__setup_affinity(self.affinity, args=args)
        logger.info("Starting: %s", args)
        self.process_start_time = time.time()
        self.process_stderr_file = self.core.mkstemp(".log", "pandora_")
        self.core.add_artifact_file(self.process_stderr_file)
        self.process_stderr = open(self.process_stderr_file, 'w')
        try:
            self.process = subprocess.Popen(
                args,
                stderr=self.process_stderr,
                stdout=self.process_stderr,
                close_fds=True)
        except OSError:
            logger.debug(
                "Unable to start Pandora binary. Args: %s", args, exc_info=True)
            raise RuntimeError(
                "Unable to start Pandora binary and/or file does not exist: %s" % args)

    def is_test_finished(self):
        retcode = self.process.poll()
        if retcode is not None and retcode == 0:
            logger.info("Pandora subprocess done its work successfully and finished w/ retcode 0")
            self.output_finished.set()
            return retcode
        elif retcode is not None and retcode != 0:
            logger.error("Pandora finished with non-zero retcode.")
            err = None
            # trying to make pandora error to look pretty in tank log
            # iterating through pandora log file backwards searching for last error
            # we look for \tERROR\t or \tFATAL\t in the string
            with FileLinesBackwardsIterator(self.process_stderr_file) as pandora_log:
                while err is None:
                    try:
                        line = next(pandora_log)
                    except StopIteration:
                        break
                    if '\tERROR\t' in line or '\tFATAL\t' in line:
                        try:
                            err = json.loads(line.split('\t')[-1])
                        except:
                            err = line
            if err is not None:
                logger.error(pprint.pformat(err))
            else:
                lines_amount = 30
                logger.error("Last %s logs of Pandora log:", lines_amount)
                self.output_finished.set()
                last_log_contents = tail_lines(self.process_stderr_file, lines_amount)
                for logline in last_log_contents:
                    logger.error(logline.strip('\n'))
            return abs(retcode)
        else:
            return -1

    def end_test(self, retcode):
        if self.process and self.process.poll() is None:
            logger.warning(
                "Terminating worker process with PID %s", self.process.pid)
            self.process.terminate()
            if self.process_stderr:
                self.process_stderr.close()
        else:
            logger.debug("Seems subprocess finished OK")
        self.output_finished.set()
        return retcode

    def post_process(self, retcode):
        if self.get_option('delete_report'):
            if self.sample_log in self.core.artifact_files:
                del self.core.artifact_files[self.sample_log]
            os.remove(self.sample_log)
        return retcode


class PandoraInfoWidget(AbstractInfoWidget):
    """ Right panel widget """

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
        text = " Pandora Test %s" % next(self.krutilka)
        space = screen.right_panel_width - len(text) - 1
        left_spaces = space // 2
        right_spaces = space // 2

        dur_seconds = int(time.time()) - int(self.owner.process_start_time)
        duration = str(datetime.timedelta(seconds=dur_seconds))

        template = screen.markup.BG_BROWN + '~' * left_spaces + \
            text + ' ' + '~' * right_spaces + screen.markup.RESET + "\n"
        template += "Command Line: %s\n"
        template += "    Duration: %s\n"
        template += "  Requests/s: %s\n"
        template += " Active reqs: %s\n"
        template += "      Target: %s\n"
        template += "    Schedule: \n%s\n"
        data = (
            self.owner.pandora_cmd,
            duration,
            self.reqps,
            self.active,
            self.owner.address,
            yaml.dump(self.owner.schedule)
        )

        return template % data
