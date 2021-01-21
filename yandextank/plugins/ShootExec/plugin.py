import errno
import collections
import logging
import os.path
import subprocess
import time

from ...common.interfaces import AbstractPlugin, GeneratorPlugin, AggregateResultListener, AbstractInfoWidget, \
    StatsReader
from ...common.util import FileScanner
from ..Console import Plugin as ConsolePlugin
from ..Phantom import PhantomReader


_INFO = collections.namedtuple(
    "Info",
    "address, port, instances, ammo_count, loop_count, duration, steps, stat_log, rps_schedule, ammo_file"
)
_LOGGER = logging.getLogger(__name__)

_PROCESS_KILL_TIMEOUT = 10  # Kill running process after specified number of seconds
_OUTPUT_WAIT_TIMEOUT = 10  # Output files should be found after specified number of seconds


class Plugin(GeneratorPlugin):
    """Simple executor of shooting process with phantom compatible output"""

    SECTION = 'shootexec'

    def __init__(self, core, cfg, name):
        AbstractPlugin.__init__(self, core, cfg, name)
        self.stats_reader = None
        self.reader = None
        self.__process = None
        self.__stderr_file = None
        self.__processed_ammo_count = 0
        self.start_time = 0
        self.opened_file = None

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        return ["cmd", "output_path", "stats_path"]

    def configure(self):
        self.__cmd = self.get_option("cmd")

        self.__output_path = self.get_option("output_path")
        self.core.add_artifact_file(self.__output_path)

        self.__stats_path = self.get_option("stats_path")
        if self.__stats_path:
            self.core.add_artifact_file(self.__stats_path)

    def get_reader(self):
        if self.reader is None:
            # Touch output_path to clear it
            open(self.__output_path, "w").close()
            self.opened_file = open(self.__output_path, 'r')
            self.add_cleanup(lambda: self.opened_file.close())
            self.reader = PhantomReader(self.opened_file)
        return self.reader

    def get_stats_reader(self):
        if self.stats_reader is None:
            self.stats_reader = _FileStatsReader(self.__stats_path) if self.__stats_path else _DummyStatsReader()
        return self.stats_reader

    def prepare_test(self):
        stderr_path = self.core.mkstemp(".log", "shootexec_stdout_stderr_")
        self.__stderr_file = open(stderr_path, 'w')

        _LOGGER.debug("Linking sample reader to aggregator. Reading samples from %s", self.__output_path)

        self.start_time = time.time()
        self.core.job.aggregator.add_result_listener(self)

        try:
            console = self.core.get_plugin_of_type(ConsolePlugin)
        except Exception as ex:
            _LOGGER.debug("Console not found: %s", ex)
            console = None

        if console:
            widget = _InfoWidget(self)
            console.add_info_widget(widget)
            self.core.job.aggregator.add_result_listener(widget)

    def start_test(self):
        _LOGGER.info("Starting shooting process: '%s'", self.__cmd)
        self.__process = subprocess.Popen(
            self.__cmd,
            shell=True,
            stderr=self.__stderr_file,
            stdout=self.__stderr_file,
            close_fds=True
        )

        # Ensure that all expected output files are ready to use
        _LOGGER.info("Waiting until output files are ready")
        waitfor = time.time() + _OUTPUT_WAIT_TIMEOUT
        while time.time() < waitfor:
            output_path_is_ready = os.path.isfile(self.__output_path)
            stats_path_is_ready = (not self.__stats_path or os.path.isfile(self.__stats_path))
            if output_path_is_ready and stats_path_is_ready:
                break
            time.sleep(0.1)
        else:
            raise Exception("Failed to wait until output resources are ready: output={}, stats={}".format(
                output_path_is_ready,
                stats_path_is_ready
            ))
        _LOGGER.info("Shooting proces is ready to use")

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
            time.time() - self.start_time,
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


class _FileStatsReader(FileScanner, StatsReader):
    """
    Read shooting stats line by line

    Line format is 'timestamp\trps\tinstances'
    """

    def __init__(self, *args, **kwargs):
        super(_FileStatsReader, self).__init__(*args, **kwargs)
        self.__last_ts = 0

    def _read_data(self, lines):
        """
        Parse lines and return stats
        """

        results = []
        for line in lines:
            timestamp, rps, instances = line.split("\t")
            curr_ts = int(float(timestamp))  # We allow floats here, but tank expects only seconds
            if self.__last_ts < curr_ts:
                self.__last_ts = curr_ts
                results.append(self.stats_item(self.__last_ts, float(rps), float(instances)))
        return results


class _DummyStatsReader(StatsReader):
    """
    Dummy stats reader for shooters without stats file
    """

    def __init__(self):
        self.__closed = False
        self.__last_ts = 0

    def __iter__(self):
        while not self.__closed:
            cur_ts = int(time.time())
            if cur_ts > self.__last_ts:
                yield [self.stats_item(cur_ts, 0, 0)]
                self.__last_ts = cur_ts
            else:
                yield []

    def close(self):
        self.__closed = True
