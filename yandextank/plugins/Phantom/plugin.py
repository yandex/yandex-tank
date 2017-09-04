""" Contains Phantom Plugin, Console widgets, result reader classes """
# FIXME: 3 there is no graceful way to interrupt the process of phout import
# TODO: phout import
import logging
import multiprocessing as mp
import subprocess
import time

from ...common.util import execute, expand_to_seconds
from ...common.interfaces import AbstractPlugin, AbstractCriterion, GeneratorPlugin

from .reader import PhantomReader, PhantomStatsReader
from .utils import PhantomConfig
from .widget import PhantomInfoWidget, PhantomProgressBarWidget
from ..Aggregator import Plugin as AggregatorPlugin
from ..Autostop import Plugin as AutostopPlugin
from ..Console import Plugin as ConsolePlugin

logger = logging.getLogger(__name__)


class Plugin(AbstractPlugin, GeneratorPlugin):
    """     Plugin for running phantom tool    """

    OPTION_CONFIG = "config"

    def __init__(self, core, cfg, cfg_updater):
        AbstractPlugin.__init__(self, core, cfg, cfg_updater)
        self.process = None

        self.predefined_phout = None
        self.did_phout_import_try = False

        self.eta_file = None
        self.processed_ammo_count = 0
        self.phantom_start_time = time.time()
        self.buffered_seconds = "2"
        self.cpu_count = mp.cpu_count()

        self.cached_info = None
        self.phantom_stderr = None

        self.exclude_markers = []
        self._stat_log = None
        self._phantom = None

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
        self.enum_ammo = self.get_option("enum_ammo", False)
        self.buffered_seconds = int(
            self.get_option("buffered_seconds", self.buffered_seconds))

        try:
            autostop = self.core.get_plugin_of_type(AutostopPlugin)
            autostop.add_criterion_class(UsedInstancesCriterion)
        except KeyError:
            logger.debug(
                "No autostop plugin found, not adding instances criterion")

        self.predefined_phout = self.get_option(PhantomConfig.OPTION_PHOUT, '')
        if not self.get_option(
                self.OPTION_CONFIG, '') and self.predefined_phout:
            self.phout_import_mode = True

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

    def prepare_test(self):
        aggregator = self.core.job.aggregator_plugin

        args = [self.get_option("phantom_path"), 'check', self.phantom.config_file]

        try:
            result = execute(args, catch_out=True)
        except OSError:
            raise RuntimeError("Phantom I/O engine is not installed!")

        retcode = result[0]
        if retcode:
            raise RuntimeError(
                "Config check failed. Subprocess returned code %s" %
                retcode)
        if result[2]:
            raise RuntimeError(
                "Subprocess returned message: %s" % result[2])
        reader = PhantomReader(self.phantom.phout_file)
        logger.debug(
            "Linking sample reader to aggregator."
            " Reading samples from %s", self.phantom.phout_file)

        logger.debug(
            "Linking stats reader to aggregator."
            " Reading stats from %s", self.phantom.stat_log)

        if aggregator:
            aggregator.reader = reader
            info = self.phantom.get_info()
            aggregator.stats_reader = PhantomStatsReader(
                self.stat_log, info)

            aggregator.add_result_listener(self)
        try:
            console = self.core.get_plugin_of_type(ConsolePlugin)
        except Exception as ex:
            logger.debug("Console not found: %s", ex)
            console = None

        self.core.job.phantom_info = self.phantom.get_info()

        if console and aggregator:
            widget = PhantomProgressBarWidget(self)
            console.add_info_widget(widget)
            aggregator.add_result_listener(widget)

            widget = PhantomInfoWidget(self)
            console.add_info_widget(widget)
            aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
            aggregator.add_result_listener(widget)

    def start_test(self):
        args = [self.get_option("phantom_path"), 'run', self.phantom.config_file]
        logger.debug(
            "Starting %s with arguments: %s", self.get_option("phantom_path"), args)
        affinity = self.get_option('affinity')
        if affinity != '':
            args = [
                self.core.taskset_path, '-c', affinity
            ] + args
            logger.debug(
                "Enabling taskset for phantom with affinity: %s,"
                " cores count: %d", affinity, self.cpu_count)
        self.phantom_start_time = time.time()
        phantom_stderr_file = self.core.mkstemp(
            ".log", "phantom_stdout_stderr_")
        self.core.add_artifact_file(phantom_stderr_file)
        self.phantom_stderr = open(phantom_stderr_file, 'w')
        self.process = subprocess.Popen(
            args,
            stderr=self.phantom_stderr,
            stdout=self.phantom_stderr,
            close_fds=True)

    def is_test_finished(self):
        retcode = self.process.poll()
        if retcode is not None:
            logger.info("Phantom done its work with exit code: %s", retcode)
            return abs(retcode)
        else:
            info = self.get_info()
            if info:
                eta = int(info.duration) - (
                    int(time.time()) - int(self.phantom_start_time))
                self.publish('eta', eta)
            return -1

    def end_test(self, retcode):
        if self.process and self.process.poll() is None:
            logger.warn(
                "Terminating phantom process with PID %s", self.process.pid)
            self.process.terminate()
            if self.process:
                self.process.communicate()
        else:
            logger.debug("Seems phantom finished OK")
        if self.phantom_stderr:
            self.phantom_stderr.close()
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


class UsedInstancesCriterion(AbstractCriterion):
    """
    Autostop criterion, based on active instances count
    """
    RC_INST = 24

    @staticmethod
    def get_type_string():
        return 'instances'

    def __init__(self, autostop, param_str):
        AbstractCriterion.__init__(self)
        self.seconds_count = 0
        self.autostop = autostop
        self.threads_limit = 1

        level_str = param_str.split(',')[0].strip()
        if level_str[-1:] == '%':
            self.level = float(level_str[:-1]) / 100
            self.is_relative = True
        else:
            self.level = int(level_str)
            self.is_relative = False
        self.seconds_limit = expand_to_seconds(param_str.split(',')[1])

        try:
            phantom = autostop.core.get_plugin_of_type(Plugin)
            info = phantom.get_info()
            if info:
                self.threads_limit = info.instances
            if not self.threads_limit:
                raise ValueError(
                    "Cannot create 'instances' criterion"
                    " with zero instances limit")
        except KeyError:
            logger.warning("No phantom module, 'instances' autostop disabled")

    def notify(self, data, stat):
        threads = stat["metrics"]["instances"]
        if self.is_relative:
            threads = float(threads) / self.threads_limit
        if threads > self.level:
            if not self.seconds_count:
                self.cause_second = (data, stat)

            logger.debug(self.explain())

            self.seconds_count += 1
            self.autostop.add_counting(self)
            if self.seconds_count >= self.seconds_limit:
                return True
        else:
            self.seconds_count = 0

        return False

    def get_rc(self):
        return self.RC_INST

    def get_level_str(self):
        """
        String value for instances level
        """
        if self.is_relative:
            level_str = str(100 * self.level) + "%"
        else:
            level_str = self.level
        return level_str

    def explain(self):
        items = (
            self.get_level_str(), self.seconds_count,
            self.cause_second[0].get('ts'))
        return (
            "Testing threads (instances) utilization"
            " higher than %s for %ss, since %s" % items)

    def widget_explain(self):
        items = (self.get_level_str(), self.seconds_count, self.seconds_limit)
        return "Instances >%s for %s/%ss" % items, float(
            self.seconds_count) / self.seconds_limit
