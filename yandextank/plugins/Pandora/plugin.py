import datetime
import logging
import subprocess
import time
import os
import shutil
from threading import Event

import yaml

from netort.resource import manager as resource_manager
from netort.resource import HttpOpener

from .reader import PandoraStatsReader
from ..Console import Plugin as ConsolePlugin
from ..Console import screen as ConsoleScreen
from ..Phantom import PhantomReader, string_to_df
from ...common.interfaces import AbstractInfoWidget, GeneratorPlugin
from ...common.util import tail_lines, FileMultiReader

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
        self.pandora_cmd = None
        self.pandora_config_file = None
        self.config_contents = None
        self.custom_config = False
        self.expvar = self.get_option('expvar')
        self.expvar_enabled = self.expvar
        self.expvar_port = self.DEFAULT_EXPVAR_PORT
        self.report_files = None
        self.__address = None
        self.__schedule = None
        self.ammofile = None
        self.process_stderr_file = None
        self.resources = []

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
        self.report_files = [self.get_option("report_file")]
        self.buffered_seconds = self.get_option("buffered_seconds")
        self.affinity = self.get_option("affinity", "")
        self.resources = self.get_option("resources")

        # if we use custom pandora binary, we can download it and make it executable
        self.pandora_cmd = self.get_resource(self.get_option("pandora_cmd"), "./pandora", permissions=0o755)

        # download all resources from self.get_options("resources")
        if len(self.resources) > 0:
            for resource in self.resources:
                self.get_resource(resource["src"], resource["dst"])

        # get config_contents and patch it: expand resources via resource manager
        # config_content option has more priority over config_file
        if self.get_option("config_content"):
            logger.info('Found config_content option configuration')
            self.config_contents = self.__patch_raw_config_and_dump(self.get_option("config_content"))
        elif self.get_option("config_file"):
            logger.info('Found config_file option configuration')
            with open(self.get_option("config_file"), 'rb') as config:
                external_file_config_contents = yaml.load(config.read(), Loader=yaml.FullLoader)
            self.config_contents = self.__patch_raw_config_and_dump(external_file_config_contents)
        else:
            raise RuntimeError("Neither pandora.config_content, nor pandora.config_file specified")
        logger.debug('Config after parsing for patching: %s', self.config_contents)

        # find report filename and add to artifacts
        self.report_files = [pool['result']['destination'] for pool in self.config_contents['pools']]
        for f in self.report_files:
            with open(f, 'w'):
                pass
            self.core.add_artifact_file(f)

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
                self.expvar_enabled = config["monitoring"]["expvar"].get("enabled")
                if config["monitoring"]["expvar"].get("port"):
                    self.expvar_port = config["monitoring"]["expvar"].get("port")
        # or set if expvar not exists
        elif not self.expvar:
            config["monitoring"] = {
                "expvar": {
                    "enabled": True,
                }
            }
            self.expvar_enabled = True

        # FIXME this is broken for custom ammo providers due to interface incompatibility
        # FIXME refactor pandora plx
        for n, pool in enumerate(config['pools']):
            if pool.get('ammo', {}).get('file', ''):
                self.ammofile = pool['ammo']['file']
                opener = resource_manager.get_opener(self.ammofile)
                if isinstance(opener, HttpOpener):
                    pool['ammo']['file'] = opener.download_file(True, try_ungzip=True)
                else:
                    pool['ammo']['file'] = opener.get_filename

            if not pool.get('result') or 'phout' not in pool.get('result', {}).get('type', ''):
                logger.warning('Seems like pandora result file not specified... adding defaults')
                pool['result'] = dict(
                    destination=f"{n}_{self.DEFAULT_REPORT_FILE}",
                    type='phout',
                )
        return config

    @property
    def address(self):
        if not self.__address:
            for pool in self.config_contents['pools']:
                if pool.get('gun', {}).get('target'):
                    self.__address = pool.get('gun', {}).get('target')
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

    def get_reader(self, parser=string_to_df):
        if self.reader is None:
            self.reader = [FileMultiReader(f, self.output_finished) for f in self.report_files]
        return [PhantomReader(reader.get_file(), parser=parser) for reader in self.reader]

    def get_stats_reader(self):
        if self.stats_reader is None:
            self.stats_reader = PandoraStatsReader(self.expvar_enabled, self.expvar_port)
        return self.stats_reader

    def get_resource(self, resource, dst, permissions=0o644):
        opener = resource_manager.get_opener(resource)
        if isinstance(opener, HttpOpener):
            tmp_path = opener.download_file(True, try_ungzip=True)
            shutil.copy(tmp_path, dst)
            logger.info('Successfully moved resource %s', dst)
        else:
            dst = opener.get_filename
        try:
            os.chmod(dst, permissions)
        except OSError:
            logger.warning('Cannot change permissions to %s', dst)
        return dst

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
        args = [self.pandora_cmd] +\
            (['-expvar'] if self.expvar else []) +\
            [self.pandora_config_file]
        if self.affinity:
            self.core.__setup_affinity(self.affinity, args=args)
        logger.info("Starting: %s", args)
        self.start_time = time.time()
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
            lines_amount = 20
            logger.info("Pandora finished with non-zero retcode. Last %s logs of Pandora log:", lines_amount)
            self.output_finished.set()
            last_log_contents = tail_lines(self.process_stderr_file, lines_amount)
            for logline in last_log_contents:
                logger.info(logline.strip('\n'))
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
        text = " Pandora Test %s" % next(self.krutilka)
        space = screen.right_panel_width - len(text) - 1
        left_spaces = space // 2
        right_spaces = space // 2

        dur_seconds = int(time.time()) - int(self.owner.start_time)
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
