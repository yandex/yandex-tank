''' Contains Universal Plugin for phout-compatible shooter '''
from Aggregator import AggregatorPlugin, AggregateResultListener
from Phantom import PhantomReader
from yandextank.core import AbstractPlugin
import subprocess
import time
import shlex
from ConsoleOnline import ConsoleOnlinePlugin, AbstractInfoWidget
import ConsoleScreen
import datetime

class UniversalPhoutShooterPlugin(AbstractPlugin, AggregateResultListener):
    '''     Plugin for running any script tool    '''

    OPTION_CONFIG = "config"
    SECTION = 'uniphout'

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.buffered_seconds=2
        self.process=None
        self.process_stderr = None
        self.process_start_time = None

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        opts = ["cmdline", "buffered_seconds", ]
        return opts

    def configure(self):
        # plugin part
        self.cmdline = self.get_option("cmdline")
        self.buffered_seconds = int(self.get_option("buffered_seconds", self.buffered_seconds))

        self.phout = self.get_option("phout", "")
        if not self.phout:
            self.phout=self.core.mkstemp(".phout", "results_")
            # TODO: pass generated phout to the script

        self.core.add_artifact_file(self.phout)

    def prepare_test(self):
        aggregator = None
        try:
            aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        except Exception, ex:
            self.log.warning("No aggregator found: %s", ex)

        if aggregator:
            aggregator.reader = PhantomReader(aggregator, self)
            aggregator.reader.buffered_seconds = self.buffered_seconds
            aggregator.add_result_listener(self)
            aggregator.reader.phout_file = self.phout

        try:
            console = self.core.get_plugin_of_type(ConsoleOnlinePlugin)
        except Exception, ex:
            self.log.debug("Console not found: %s", ex)
            console = None

        if console:
            widget = UniphoutInfoWidget(self)
            console.add_info_widget(widget)
            aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
            aggregator.add_result_listener(widget)


    def start_test(self):
        args = shlex.split(self.cmdline)
        self.log.info("Starting: %s", args)
        self.process_start_time = time.time()
        process_stderr_file = self.core.mkstemp(".log", "phantom_stdout_stderr_")
        self.core.add_artifact_file(process_stderr_file)
        self.process_stderr = open(process_stderr_file, 'w')
        self.process = subprocess.Popen(args, stderr=self.process_stderr, stdout=self.process_stderr, close_fds=True)


    def is_test_finished(self):
        retcode = self.process.poll()
        if retcode != None:
            self.log.info("Subprocess done its work with exit code: %s", retcode)
            return abs(retcode)
        else:
            return -1


    def end_test(self, retcode):
        if self.process and self.process.poll() == None:
            self.log.warn("Terminating worker process with PID %s", self.process.pid)
            self.process.terminate()
            if self.process_stderr:
                self.process_stderr.close()
        else:
            self.log.debug("Seems subprocess finished OK")
        return retcode

    def get_info(self):
        return None

    def aggregate_second(self, second_aggregate_data):
        pass


class UniphoutInfoWidget(AbstractInfoWidget):
    ''' Right panel widget '''
    def __init__(self, uniphout):
        AbstractInfoWidget.__init__(self)
        self.krutilka = ConsoleScreen.krutilka()
        self.owner = uniphout
        self.rps = 0

    def get_index(self):
        return 0

    def aggregate_second(self, second_aggregate_data):
        self.active_threads = second_aggregate_data.overall.active_threads
        self.rps = second_aggregate_data.overall.RPS

    def render(self, screen):
        text = " Uniphout Test %s" % self.krutilka.next()
        space = screen.right_panel_width - len(text) - 1
        left_spaces = space / 2
        right_spaces = space / 2

        dur_seconds = int(time.time()) - int(self.owner.process_start_time)
        duration = str(datetime.timedelta(seconds=dur_seconds))

        template = screen.markup.BG_BROWN + '~' * left_spaces + text + ' ' + '~' * right_spaces + screen.markup.RESET + "\n"
        template += "Command Line: %s\n"
        template += "    Duration: %s\n"
        template += " Responses/s: %s"
        data = (self.owner.cmdline, duration, self.rps)

        return template % data
