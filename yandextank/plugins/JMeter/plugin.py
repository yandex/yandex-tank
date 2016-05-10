""" jmeter load generator support """
import logging
import os
import signal
import subprocess
import time
import datetime
from pkg_resources import resource_string

from ...core.util import splitstring
from ...core.interfaces import AbstractPlugin, AggregateResultListener, AbstractInfoWidget
from ..Aggregator import AggregatorPlugin
from ..Console import ConsolePlugin
from ..Console import screen as ConsoleScreen
from .reader import JMeterReader

logger = logging.getLogger(__name__)


class JMeterPlugin(AbstractPlugin):
    """ JMeter tank plugin """
    SECTION = 'jmeter'

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.jmeter_process = None
        self.args = None
        self.original_jmx = None
        self.jtl_file = None
        self.jmx = None
        self.user_args = None
        self.jmeter_path = None
        self.jmeter_log = None
        self.start_time = time.time()
        self.jmeter_buffer_size = None
        self.use_argentum = None

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        return ["jmx", "args", "jmeter_path", "buffer_size",
                "buffered_seconds", "exclude_markers"]

    def configure(self):
        self.original_jmx = self.get_option("jmx")
        self.core.add_artifact_file(self.original_jmx, True)
        self.jtl_file = self.core.mkstemp('.jtl', 'jmeter_')
        self.core.add_artifact_file(self.jtl_file)
        self.user_args = self.get_option("args", '')
        self.jmeter_path = self.get_option("jmeter_path", 'jmeter')
        self.jmeter_log = self.core.mkstemp('.log', 'jmeter_')
        self.jmeter_buffer_size = int(self.get_option(
            'buffer_size', self.get_option('buffered_seconds', '3')))
        self.core.add_artifact_file(self.jmeter_log, True)
        self.use_argentum = eval(self.get_option('use_argentum', 'False'))
        self.exclude_markers = set(filter(
            (lambda marker: marker != ''), self.get_option('exclude_markers',
                                                           []).split(' ')))
        self.jmx = self.__add_jmeter_components(
            self.original_jmx, self.jtl_file, self._get_variables())
        self.core.add_artifact_file(self.jmx)

    def prepare_test(self):
        self.args = [self.jmeter_path, "-n", "-t", self.jmx, '-j',
                     self.jmeter_log,
                     '-Jjmeter.save.saveservice.default_delimiter=\\t',
                     '-Jjmeter.save.saveservice.connect_time=true']
        self.args += splitstring(self.user_args)

        aggregator = None
        try:
            aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        except Exception, ex:
            logger.warning("No aggregator found: %s", ex)

        if aggregator:
            aggregator.reader = JMeterReader(self.jtl_file)
            aggregator.stats_reader = aggregator.reader.stats_reader

        try:
            console = self.core.get_plugin_of_type(ConsolePlugin)
        except Exception, ex:
            logger.debug("Console not found: %s", ex)
            console = None

        if console:
            widget = JMeterInfoWidget(self)
            console.add_info_widget(widget)
            if aggregator:
                aggregator.add_result_listener(widget)

    def start_test(self):
        logger.info("Starting %s with arguments: %s", self.jmeter_path,
                    self.args)
        self.jmeter_process = subprocess.Popen(
            self.args,
            executable=self.jmeter_path,
            preexec_fn=os.setsid,
            close_fds=True)  # stderr=subprocess.PIPE, stdout=subprocess.PIPE,
        self.start_time = time.time()

    def is_test_finished(self):
        retcode = self.jmeter_process.poll()
        if retcode is not None:
            logger.info("JMeter process finished with exit code: %s", retcode)
            return retcode
        else:
            return -1

    def end_test(self, retcode):
        if self.jmeter_process:
            logger.info("Terminating jmeter process group with PID %s",
                        self.jmeter_process.pid)
            try:
                os.killpg(self.jmeter_process.pid, signal.SIGTERM)
            except OSError, exc:
                logger.debug("Seems JMeter exited itself: %s", exc)
                # Utils.log_stdout_stderr(logger, self.jmeter_process.stdout, self.jmeter_process.stderr, "jmeter")

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
        except Exception, exc:
            raise RuntimeError("Failed to find the end of JMX XML: %s" % exc)

        tpl_resource = 'jmeter_writer.xml'

        if self.use_argentum:
            logger.warn(
                "You are using argentum aggregator for JMeter. Be careful.")
            tpl_resource = 'jmeter_argentum.xml'

        tpl = resource_string(__name__, 'config/' + tpl_resource)
        udv_tpl = resource_string(__name__, 'config/jmeter_var_template.xml')

        udv_set = []
        for var_name, var_value in variables.iteritems():
            udv_set.append(udv_tpl % (var_name, var_name, var_value))

        try:
            new_file = self.core.mkstemp(
                '.jmx', 'modified_', os.path.dirname(os.path.realpath(jmx)))
        except OSError, exc:
            logger.debug("Can't create modified jmx near original: %s", exc)
            new_file = self.core.mkstemp('.jmx', 'modified_')
        logger.debug("Modified JMX: %s", new_file)
        file_handle = open(new_file, "wb")
        file_handle.write(''.join(source_lines))
        file_handle.write(tpl % (jtl, "\n".join(udv_set)))
        file_handle.write(closing)
        file_handle.close()
        return new_file

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
        data = (os.path.basename(self.jmeter.original_jmx), duration,
                self.active_threads, self.RPS)

        return template % data
