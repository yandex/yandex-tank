""" jmeter load generator support """
import datetime
import logging
import os
import signal
import subprocess
import time
import socket
import re
import shlex

from pkg_resources import resource_string

from .reader import JMeterReader
from ..Console import Plugin as ConsolePlugin
from ..Console import screen as ConsoleScreen
from ...common.interfaces import AggregateResultListener, AbstractInfoWidget, GeneratorPlugin

logger = logging.getLogger(__name__)


class Plugin(GeneratorPlugin):
    """ JMeter tank plugin """
    SECTION = 'jmeter'
    SHUTDOWN_TEST = 'Shutdown'
    STOP_TEST_NOW = 'Stop Test'
    DISCOVER_PORT_PATTERN = r'Waiting for possible .* message on port (?P<port>\d+)'

    def __init__(self, core, cfg, name):
        super(Plugin, self).__init__(core, cfg, name)
        self.args = None
        self.original_jmx = None
        self.jtl_file = None
        self.ext_log = None
        self.ext_levels = ['none', 'errors', 'all']
        self.ext_log_file = None
        self.jmx = None
        self.user_args = None
        self.jmeter_path = None
        self.jmeter_ver = None
        self.jmeter_log = None
        self.start_time = time.time()
        self.jmeter_buffer_size = None
        self.jmeter_udp_port = None
        self.shutdown_timeout = None

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        return [
            "jmx", "args", "jmeter_path", "buffer_size", "buffered_seconds",
            "exclude_markers", "shutdown_timeout"
        ]

    def configure(self):
        self.original_jmx = self.get_option("jmx")
        self.core.add_artifact_file(self.original_jmx, True)
        self.jtl_file = self.core.mkstemp('.jtl', 'jmeter_')
        self.core.add_artifact_file(self.jtl_file)
        self.user_args = self.get_option("args", '')
        self.jmeter_path = self.get_option('jmeter_path')
        self.jmeter_log = self.core.mkstemp('.log', 'jmeter_')
        self.jmeter_ver = self.get_option('jmeter_ver')
        self.ext_log = self.get_option('extended_log', self.get_option('ext_log'))

        if self.ext_log != 'none':
            self.ext_log_file = self.core.mkstemp('.jtl', 'jmeter_ext_')
            self.core.add_artifact_file(self.ext_log_file)

        self.core.add_artifact_file(self.jmeter_log, True)
        self.exclude_markers = set(self.get_option('exclude_markers', []))
        self.jmx = self.__add_jmeter_components(
            self.original_jmx, self.jtl_file, self.get_option('variables'))
        self.core.add_artifact_file(self.jmx)

        jmeter_stderr_file = self.core.mkstemp(".log", "jmeter_stdout_stderr_")
        self.core.add_artifact_file(jmeter_stderr_file)
        self.process_stderr = open(jmeter_stderr_file, 'w')
        self.shutdown_timeout = self.get_option('shutdown_timeout', 3)

        self.affinity = self.get_option('affinity', '')

    def get_reader(self):
        if self.reader is None:
            self.reader = JMeterReader(self.jtl_file)
        return self.reader

    def get_stats_reader(self):
        if self.stats_reader is None:
            self.stats_reader = self.reader.stats_reader
        return self.stats_reader

    def prepare_test(self):
        self.args = [
            self.jmeter_path, "-n", "-t", self.jmx, '-j', self.jmeter_log,
            '-Jjmeter.save.saveservice.default_delimiter=\\t',
            '-Jjmeter.save.saveservice.connect_time=true'
        ]
        self.args += shlex.split(self.user_args)

        if self.affinity:
            self.core.__setup_affinity(self.affinity, args=self.args)

        try:
            console = self.core.get_plugin_of_type(ConsolePlugin)
        except Exception as ex:
            logger.debug("Console not found: %s", ex)
            console = None

        if console:
            widget = JMeterInfoWidget(self)
            console.add_info_widget(widget)
            self.core.job.aggregator.add_result_listener(widget)

    def start_test(self):
        logger.info(
            "Starting %s with arguments: %s", self.jmeter_path, self.args)
        try:
            self.process = subprocess.Popen(
                self.args,
                executable=self.jmeter_path,
                preexec_fn=os.setsid,
                close_fds=True,
                stdout=self.process_stderr,
                stderr=self.process_stderr)
        except OSError:
            logger.debug(
                "Unable to start JMeter process. Args: %s, Executable: %s",
                self.args,
                self.jmeter_path,
                exc_info=True)
            raise RuntimeError(
                "Unable to access to JMeter executable file or it does not exist: %s"
                % self.jmeter_path)
        self.start_time = time.time()
        self.jmeter_udp_port = self.__discover_jmeter_udp_port()

    def is_test_finished(self):
        retcode = self.process.poll()
        aggregator = self.core.job.aggregator
        if not aggregator.reader.jmeter_finished and retcode is not None:
            logger.info(
                "JMeter process finished with exit code: %s, waiting for aggregator",
                retcode)
            self.retries = 0
            aggregator.reader.jmeter_finished = True
            return -1
        elif aggregator.reader.jmeter_finished is True:
            if aggregator.reader.agg_finished:
                self.reader.close()
                return retcode
            else:
                logger.info("Waiting for aggregator to finish")
                return -1
        else:
            return -1

    def end_test(self, retcode):
        if self.process:
            gracefully_shutdown = self.__graceful_shutdown()
            if not gracefully_shutdown:
                self.__kill_jmeter()
        if self.process_stderr:
            self.process_stderr.close()
        self.core.add_artifact_file(self.jmeter_log)
        self.reader.close()
        return retcode

    def __discover_jmeter_udp_port(self):
        """Searching for line in jmeter.log such as
        Waiting for possible shutdown message on port 4445
        """
        r = re.compile(self.DISCOVER_PORT_PATTERN)
        with open(self.process_stderr.name, 'r') as f:
            cnt = 0
            while self.process.pid and cnt < 10:
                line = f.readline()
                m = r.match(line)
                if m is None:
                    cnt += 1
                    time.sleep(1)
                else:
                    port = int(m.group('port'))
                    return port
            else:
                logger.warning('JMeter UDP port wasn\'t discovered')
                return None

    def __kill_jmeter(self):
        logger.info(
            "Terminating jmeter process group with PID %s",
            self.process.pid)
        try:
            os.killpg(self.process.pid, signal.SIGTERM)
        except OSError as exc:
            logger.debug("Seems JMeter exited itself: %s", exc)
            # Utils.log_stdout_stderr(logger, self.process.stdout, self.process.stderr, "jmeter")

    def __add_jmeter_components(self, jmx, jtl, variables):
        """ Genius idea by Alexey Lavrenyuk """
        logger.debug("Original JMX: %s", os.path.realpath(jmx))
        with open(jmx, 'r') as src_jmx:
            source_lines = src_jmx.readlines()

        try:
            # In new Jmeter version (3.2 as example) WorkBench's plugin checkbox enabled by default
            # It totally crashes Yandex tank injection and raises XML Parse Exception
            closing = source_lines.pop(-1)
            if "WorkBenchGui" in source_lines[-5]:
                logger.info("WorkBench checkbox enabled...bypassing")
                last_string_count = 6
            else:
                last_string_count = 2
            while last_string_count > 0:
                closing = source_lines.pop(-1) + closing
                last_string_count -= 1
            logger.debug("Closing statement: %s", closing)
        except Exception as exc:
            raise RuntimeError("Failed to find the end of JMX XML: %s" % exc)

        udv_tpl = resource_string(__name__, 'config/jmeter_var_template.xml').decode('utf8')
        udv_set = []
        for var_name, var_value in variables.items():
            udv_set.append(udv_tpl % (var_name, var_name, var_value))
        udv = "\n".join(udv_set)

        if self.jmeter_ver >= 2.13:
            save_connect = '<connectTime>true</connectTime>'
        else:
            save_connect = ''

        if self.ext_log in ['errors', 'all']:
            level_map = {'errors': 'true', 'all': 'false'}
            tpl_resource = 'jmeter_writer_ext.xml'
            tpl_args = {
                'jtl': self.jtl_file,
                'udv': udv,
                'ext_log': self.ext_log_file,
                'ext_level': level_map[self.ext_log],
                'save_connect': save_connect
            }
        else:
            tpl_resource = 'jmeter_writer.xml'
            tpl_args = {
                'jtl': self.jtl_file,
                'udv': udv,
                'save_connect': save_connect
            }

        tpl = resource_string(__name__, 'config/' + tpl_resource).decode('utf8')

        try:
            new_jmx = self.core.mkstemp(
                '.jmx', 'modified_', os.path.dirname(os.path.realpath(jmx)))
        except OSError as exc:
            logger.debug("Can't create modified jmx near original: %s", exc)
            new_jmx = self.core.mkstemp('.jmx', 'modified_')
        logger.debug("Modified JMX: %s", new_jmx)
        with open(new_jmx, "w") as fh:
            fh.write(''.join(source_lines))
            fh.write(tpl % tpl_args)
            fh.write(closing)
        return new_jmx

    def __graceful_shutdown(self):
        if self.jmeter_udp_port is None:
            return False
        shutdown_test_started = time.time()
        while time.time() - shutdown_test_started < self.shutdown_timeout:
            self.__send_udp_message(self.SHUTDOWN_TEST)
            if self.process.poll() is not None:
                return True
            else:
                time.sleep(1)
        self.log.info('Graceful shutdown failed after %s' % str(time.time() - shutdown_test_started))

        stop_test_started = time.time()
        while time.time() - stop_test_started < self.shutdown_timeout:
            self.__send_udp_message(self.STOP_TEST_NOW)
            if self.process.poll() is not None:
                return True
            else:
                time.sleep(1)
        self.log.info('Graceful stop failed after {}'.format(time.time() - stop_test_started))
        return False

    def __send_udp_message(self, message):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(message.encode('utf8'), ('localhost', self.jmeter_udp_port))


class JMeterInfoWidget(AbstractInfoWidget, AggregateResultListener):
    """ Right panel widget with JMeter test info """

    def __init__(self, jmeter):
        AbstractInfoWidget.__init__(self)
        self.krutilka = ConsoleScreen.krutilka()
        self.jmeter = jmeter
        self.active_threads = 0
        self.RPS = 0

    def get_index(self):
        return 0

    def on_aggregated_data(self, data, stats):
        self.active_threads = stats['metrics']['instances']
        self.RPS = data['overall']['interval_real']['len']

    def render(self, screen):
        jmeter = " JMeter Test %s" % next(self.krutilka)
        space = screen.right_panel_width - len(jmeter) - 1
        left_spaces = space // 2
        right_spaces = space // 2

        dur_seconds = int(time.time()) - int(self.jmeter.start_time)
        duration = str(datetime.timedelta(seconds=dur_seconds))

        template = screen.markup.BG_MAGENTA + '~' * left_spaces + jmeter + ' '
        template += '~' * right_spaces + screen.markup.RESET + "\n"
        template += "     Test Plan: %s\n"
        template += "      Duration: %s\n"
        template += "Active Threads: %s\n"
        template += "   Responses/s: %s"
        data = (
            os.path.basename(self.jmeter.original_jmx), duration,
            self.active_threads, self.RPS)

        return template % data
