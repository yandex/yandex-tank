""" jmeter load generator support """
import datetime
import logging
import os
import signal
import subprocess
import time

from pkg_resources import resource_string
from ...common.util import splitstring
from ...common.interfaces import AbstractPlugin, AggregateResultListener, AbstractInfoWidget, GeneratorPlugin

from .reader import JMeterReader
from ..Aggregator import Plugin as AggregatorPlugin
from ..Console import Plugin as ConsolePlugin
from ..Console import screen as ConsoleScreen

logger = logging.getLogger(__name__)


class Plugin(AbstractPlugin, GeneratorPlugin):
    """ JMeter tank plugin """
    SECTION = 'jmeter'

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.jmeter_process = None
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

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        return [
            "jmx", "args", "jmeter_path", "buffer_size", "buffered_seconds",
            "exclude_markers"
        ]

    def configure(self):
        self.original_jmx = self.get_option("jmx")
        self.core.add_artifact_file(self.original_jmx, True)
        self.jtl_file = self.core.mkstemp('.jtl', 'jmeter_')
        self.core.add_artifact_file(self.jtl_file)
        self.user_args = self.get_option("args", '')
        self.jmeter_path = self.get_option('jmeter_path', 'jmeter')
        self.jmeter_log = self.core.mkstemp('.log', 'jmeter_')
        self.jmeter_ver = float(self.get_option('jmeter_ver', '3.0'))
        self.ext_log = self.get_option(
            'extended_log', self.get_option('ext_log', 'none'))
        if self.ext_log not in self.ext_levels:
            self.ext_log = 'none'
        if self.ext_log != 'none':
            self.ext_log_file = self.core.mkstemp('.jtl', 'jmeter_ext_')
            self.core.add_artifact_file(self.ext_log_file)
        self.jmeter_buffer_size = int(
            self.get_option(
                'buffer_size', self.get_option('buffered_seconds', '3')))
        self.core.add_artifact_file(self.jmeter_log, True)
        self.exclude_markers = set(
            filter((lambda marker: marker != ''),
                   self.get_option('exclude_markers', []).split(' ')))
        self.jmx = self.__add_jmeter_components(
            self.original_jmx, self.jtl_file, self._get_variables())
        self.core.add_artifact_file(self.jmx)

        jmeter_stderr_file = self.core.mkstemp(".log", "jmeter_stdout_stderr_")
        self.core.add_artifact_file(jmeter_stderr_file)
        self.jmeter_stderr = open(jmeter_stderr_file, 'w')

    def prepare_test(self):
        self.args = [
            self.jmeter_path, "-n", "-t", self.jmx, '-j', self.jmeter_log,
            '-Jjmeter.save.saveservice.default_delimiter=\\t',
            '-Jjmeter.save.saveservice.connect_time=true'
        ]
        self.args += splitstring(self.user_args)

        aggregator = None
        try:
            aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        except Exception as ex:
            logger.warning("No aggregator found: %s", ex)

        if aggregator:
            aggregator.reader = JMeterReader(self.jtl_file)
            aggregator.stats_reader = aggregator.reader.stats_reader

        try:
            console = self.core.get_plugin_of_type(ConsolePlugin)
        except Exception as ex:
            logger.debug("Console not found: %s", ex)
            console = None

        if console:
            widget = JMeterInfoWidget(self)
            console.add_info_widget(widget)
            if aggregator:
                aggregator.add_result_listener(widget)

    def start_test(self):
        logger.info(
            "Starting %s with arguments: %s", self.jmeter_path, self.args)
        try:
            self.jmeter_process = subprocess.Popen(
                self.args,
                executable=self.jmeter_path,
                preexec_fn=os.setsid,
                close_fds=True,
                stdout=self.jmeter_stderr,
                stderr=self.jmeter_stderr)
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

    def is_test_finished(self):
        retcode = self.jmeter_process.poll()
        aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        if not aggregator.reader.jmeter_finished and retcode is not None:
            logger.info(
                "JMeter process finished with exit code: %s, waiting for aggregator",
                retcode)
            self.retries = 0
            aggregator.reader.jmeter_finished = True
            return -1
        elif aggregator.reader.jmeter_finished is True:
            if aggregator.reader.agg_finished:
                return retcode
            else:
                logger.info("Waiting for aggregator to finish")
                return -1
        else:
            return -1

    def end_test(self, retcode):
        if self.jmeter_process:
            logger.info(
                "Terminating jmeter process group with PID %s",
                self.jmeter_process.pid)
            try:
                os.killpg(self.jmeter_process.pid, signal.SIGTERM)
            except OSError as exc:
                logger.debug("Seems JMeter exited itself: %s", exc)
                # Utils.log_stdout_stderr(logger, self.jmeter_process.stdout, self.jmeter_process.stderr, "jmeter")
        if self.jmeter_stderr:
            self.jmeter_stderr.close()
        self.core.add_artifact_file(self.jmeter_log)
        return retcode

    def __add_jmeter_components(self, jmx, jtl, variables):
        """ Genius idea by Alexey Lavrenyuk """
        logger.debug("Original JMX: %s", os.path.realpath(jmx))
        with open(jmx, 'r') as src_jmx:
            source_lines = src_jmx.readlines()

        try:
            closing = source_lines.pop(-1)
            closing = source_lines.pop(-1) + closing
            closing = source_lines.pop(-1) + closing
            logger.debug("Closing statement: %s", closing)
        except Exception as exc:
            raise RuntimeError("Failed to find the end of JMX XML: %s" % exc)

        udv_tpl = resource_string(__name__, 'config/jmeter_var_template.xml')
        udv_set = []
        for var_name, var_value in variables.iteritems():
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

        tpl = resource_string(__name__, 'config/' + tpl_resource)

        try:
            new_jmx = self.core.mkstemp(
                '.jmx', 'modified_', os.path.dirname(os.path.realpath(jmx)))
        except OSError as exc:
            logger.debug("Can't create modified jmx near original: %s", exc)
            new_jmx = self.core.mkstemp('.jmx', 'modified_')
        logger.debug("Modified JMX: %s", new_jmx)
        with open(new_jmx, "wb") as fh:
            fh.write(''.join(source_lines))
            fh.write(tpl % tpl_args)
            fh.write(closing)
        return new_jmx

    def _get_variables(self):
        res = {}
        for option in self.core.config.get_options(self.SECTION):
            if option[0] not in self.get_available_options():
                res[option[0]] = option[1]
        logging.debug("Variables: %s", res)
        return res


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
        jmeter = " JMeter Test %s" % self.krutilka.next()
        space = screen.right_panel_width - len(jmeter) - 1
        left_spaces = space / 2
        right_spaces = space / 2

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
