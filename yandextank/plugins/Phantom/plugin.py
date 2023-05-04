""" Contains Phantom Plugin, Console widgets, result reader classes """
# FIXME: 3 there is no graceful way to interrupt the process of phout import
# TODO: phout import
import logging
import subprocess
import time
from threading import Event

from .reader import PhantomReader, PhantomStatsReader, string_to_df
from .utils import PhantomConfig
from .widget import PhantomInfoWidget, PhantomProgressBarWidget
from ..Console import Plugin as ConsolePlugin
from ...common.interfaces import GeneratorPlugin
from ...common.util import FileMultiReader
from .log_analyzer import LogAnalyzer

from yandextank.contrib.netort.netort.process import execute

logger = logging.getLogger(__name__)


class Plugin(GeneratorPlugin):
    """     Plugin for running phantom tool    """

    OPTION_CONFIG = "config"
    SECTION = "phantom"

    def __init__(self, core, cfg, name):
        super(Plugin, self).__init__(core, cfg, name)
        self.phout_finished = Event()
        self.predefined_phout = None
        self.did_phout_import_try = False
        self.eta_file = None
        self.processed_ammo_count = 0
        self.cached_info = None
        self.exclude_markers = []
        self._stat_log = None
        self._phantom = None
        self.config = None
        self.enum_ammo = None
        self.phout_import_mode = None
        self.start_time = None

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        opts = [
            "phantom_path", "buffered_seconds", "exclude_markers", "affinity"
        ]
        opts += [PhantomConfig.OPTION_PHOUT, self.OPTION_CONFIG]
        opts += PhantomConfig.get_available_options()
        return opts

    def configure(self):
        # plugin part
        self.config = self.get_option(self.OPTION_CONFIG, '')
        self.affinity = self.get_option('affinity', '')
        self.enum_ammo = self.get_option("enum_ammo", False)
        self.buffered_seconds = int(
            self.get_option("buffered_seconds", self.buffered_seconds))

        self.predefined_phout = self.get_option(PhantomConfig.OPTION_PHOUT, '')
        if not self.get_option(self.OPTION_CONFIG, '') and self.predefined_phout:
            self.phout_import_mode = True
        self.phantom_config = self.phantom.config_file

    @property
    def phantom(self):
        """
        :rtype: PhantomConfig
        """
        if not self._phantom:
            self._phantom = PhantomConfig(self.core, self.cfg, self.stat_log)
            self._phantom.read_config()
        return self._phantom

    @property
    def stat_log(self):
        if not self._stat_log:
            self._stat_log = self.core.mkstemp(".log", "phantom_stat_")
        return self._stat_log

    def get_reader(self, parser=string_to_df):
        if self.reader is None:
            self.reader = FileMultiReader(self.phantom.phout_file, self.phout_finished)
        return PhantomReader(self.reader.get_file(), parser=parser)

    def get_stats_reader(self):
        if self.stats_reader is None:
            self.stats_reader = PhantomStatsReader(self.stat_log, self.phantom.get_info(), lambda: self.start_time)
        return self.stats_reader

    def prepare_test(self):
        try:
            retcode, stdout, stderr = execute(
                [self.get_option("phantom_path"), 'check', self.phantom.config_file], catch_out=True
            )
        except OSError:
            logger.debug("Phantom I/O engine is not installed!", exc_info=True)
            raise OSError("Phantom I/O engine not found. \nMore information: {doc_url}".format(
                doc_url='http://yandextank.readthedocs.io/en/latest/install.html')
            )
        else:
            if retcode or stderr:
                raise RuntimeError("Config check failed. Subprocess returned code %s. Stderr: %s" % (retcode, stderr))

        logger.debug(
            "Linking sample reader to aggregator."
            " Reading samples from %s", self.phantom.phout_file)

        logger.debug(
            "Linking stats reader to aggregator."
            " Reading stats from %s", self.phantom.stat_log)

        self.core.job.aggregator.add_result_listener(self)

        # stepping inside get_info()
        self.core.job.phantom_info = self.phantom.get_info()

        try:
            console = self.core.get_plugin_of_type(ConsolePlugin)
        except KeyError as ex:
            logger.debug(ex)
        else:
            widget1 = PhantomProgressBarWidget(self)
            console.add_info_widget(widget1)
            self.core.job.aggregator.add_result_listener(widget1)

            widget2 = PhantomInfoWidget(self)
            console.add_info_widget(widget2)
            self.core.job.aggregator.add_result_listener(widget2)

    def start_test(self):
        args = [self.get_option("phantom_path"), 'run', self.phantom.config_file]
        if self.affinity:
            logger.info('Enabled cpu affinity %s for phantom', self.affinity)
            args = self.core.__setup_affinity(self.affinity, args=args)
        logger.debug("Starting %s with arguments: %s", self.get_option("phantom_path"), args)
        phantom_stderr_file = self.core.mkstemp(
            ".log", "phantom_stdout_stderr_")
        self.core.add_artifact_file(phantom_stderr_file)
        self.process_stderr = open(phantom_stderr_file, 'w')
        self.start_time = time.time()
        self.process = subprocess.Popen(
            args,
            stderr=self.process_stderr,
            stdout=self.process_stderr,
            close_fds=True)

    def is_test_finished(self):
        retcode = self.process.poll()
        if retcode is not None:
            logger.info("Phantom done its work with exit code: %s", retcode)
            self.phout_finished.set()
            if retcode != 0:
                errors = LogAnalyzer(self.phantom.phantom_log).get_most_recent_errors()
                if not errors:
                    logger.error('Phantom exited with code %s but without errors in log.')
                self.errors.extend(errors)
            return abs(retcode)
        else:
            info = self.get_info()
            if info:
                eta = int(info.duration) - (int(time.time()) - int(self.start_time))
                self.publish('eta', eta)
            return -1

    def end_test(self, retcode):
        if self.process and self.process.poll() is None:
            logger.info("Terminating phantom process with PID %s", self.process.pid)
            self.process.terminate()
            if self.process:
                self.process.communicate()
        else:
            logger.debug("Seems phantom finished OK")
        self.phout_finished.set()
        if self.process_stderr:
            self.process_stderr.close()
        return retcode

    def post_process(self, retcode):
        if not retcode:
            info = self.get_info()
            if info and info.ammo_count != self.processed_ammo_count:
                logger.warning(
                    "Planned ammo count %s differs from processed %s",
                    info.ammo_count, self.processed_ammo_count)
        return retcode

    def on_aggregated_data(self, data, stat):
        self.processed_ammo_count += data["overall"]["interval_real"]["len"]
        logger.debug("Processed ammo count: %s/", self.processed_ammo_count)

    def get_info(self):
        """ returns info object """
        if not self.cached_info:
            if not self.phantom:
                return None
            self.cached_info = self.phantom.get_info()
        return self.cached_info
