import errno
import collections
import logging
import subprocess
import time

from ...common.interfaces import AbstractPlugin, GeneratorPlugin, AggregateResultListener, AbstractInfoWidget
from ..Console import Plugin as ConsolePlugin
from ..Phantom import PhantomReader


_INFO = collections.namedtuple(
    "Info",
    "address, port, instances, ammo_count, loop_count, duration, steps, stat_log, rps_schedule, ammo_file"
)
_LOGGER = logging.getLogger(__name__)

_PROCESS_KILL_TIMEOUT = 10  # Kill running process after specified number of seconds


class Plugin(AbstractPlugin, GeneratorPlugin):
    """Simple executor of shooting process with phantom compatible output"""

    SECTION = 'shootexec'

    def __init__(self, core, config, cfg_updater):
        AbstractPlugin.__init__(self, core, config, cfg_updater)
        self.__process = None
        self.__stderr_file = None
        self.__processed_ammo_count = 0
        self.__start_time = 0

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        return ["cmd", "output_path"]

    def configure(self):
        self.__cmd = self.get_option("cmd")
        self.__output_path = self.get_option("output_path")
        self.core.add_artifact_file(self.__output_path)

    def prepare_test(self):
        stderr_path = self.core.mkstemp(".log", "shootexec_stdout_stderr_")
        self.__stderr_file = open(stderr_path, 'w')

        # Touch output_path because PhantomReader wants to open it
        with open(self.__output_path, "w"):
            pass

        reader = PhantomReader(self.__output_path)
        _LOGGER.debug("Linking sample reader to aggregator. Reading samples from %s", self.__output_path)

        self.__start_time = time.time()

        aggregator = self.core.job.aggregator_plugin
        if aggregator:
            aggregator.reader = reader
            aggregator.stats_reader = _StatsReader()
            aggregator.add_result_listener(self)

        try:
            console = self.core.get_plugin_of_type(ConsolePlugin)
        except Exception as ex:
            _LOGGER.debug("Console not found: %s", ex)
            console = None

        if console and aggregator:
            widget = _InfoWidget(self)
            console.add_info_widget(widget)
            aggregator.add_result_listener(widget)

    def start_test(self):
        _LOGGER.info("Starting shooting process: '%s'", self.__cmd)
        self.__process = subprocess.Popen(
            self.__cmd,
            shell=True,
            stderr=self.__stderr_file,
            stdout=self.__stderr_file,
            close_fds=True
        )

    def is_test_finished(self):
        retcode = self.__process.poll()
        if retcode is not None:
            _LOGGER.info("Shooting process done its work with exit code: %s", retcode)
            return abs(retcode)
        else:
            return -1

    def end_test(self, retcode):
        if self.__process and self.__process.poll() is None:
            _LOGGER.warn("Terminating shooting process with PID %s", self.__process.pid)
            self.__terminate()
        else:
            _LOGGER.debug("Seems shooting process finished OK")
        return retcode

    def post_process(self, retcode):
        return retcode

    def on_aggregated_data(self, data, stats):
        self.__processed_ammo_count += data["overall"]["interval_real"]["len"]
        _LOGGER.debug("Processed ammo count: %s", self.__processed_ammo_count)

    def get_info(self):
        """ returns info object """
        return _INFO(
            "",
            "",
            "0",
            "0",
            "0",
            time.time() - self.__start_time,
            None,
            "",
            "",
            ""
        )

    def __terminate(self):
        """Gracefull termination of running process"""

        if self.__stderr_file:
            self.__stderr_file.close()

        if not self.__process:
            return

        waitfor = time.time() + _PROCESS_KILL_TIMEOUT
        while time.time() < waitfor:
            try:
                self.__process.terminate()
            except EnvironmentError as e:
                if e.errno != errno.ESRCH:
                    _LOGGER.warning("Failed to terminate process '{}': {}".format(self.__cmd, e))
                return
            time.sleep(0.1)

        try:
            self.__process.kill()
        except EnvironmentError as e:
            if e.errno != errno.ESRCH:
                _LOGGER.warning("Failed to kill process '{}': {}".format(self.__cmd, e))
            return


class _InfoWidget(AbstractInfoWidget, AggregateResultListener):
    """
    Widget with information about current run state
    """

    def get_index(self):
        return 2

    def __init__(self, sender):
        AbstractInfoWidget.__init__(self)
        self.owner = sender

    def render(self, screen):
        return ""

    def on_aggregated_data(self, data, stats):
        pass


class _StatsReader(object):

    def __init__(self):
        self.__closed = False
        self.__last_ts = 0

    def __iter__(self):
        while not self.__closed:
            cur_ts = int(time.time())
            if cur_ts > self.__last_ts:
                yield [{
                    'ts': cur_ts,
                    'metrics': {
                        'instances': 0,
                        'reqps': 0,
                    },
                }]
                self.__last_ts = cur_ts
            else:
                yield []

    def close(self):
        self.__closed = True
