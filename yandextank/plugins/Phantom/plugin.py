""" Contains Phantom Plugin, Console widgets, result reader classes """
# FIXME: 3 there is no graceful way to interrupt the process of phout import
import json
import os
import socket
import subprocess
import sys
import time
import datetime
import string
import multiprocessing as mp

import yandextank.plugins.Console.screen as ConsoleScreen
from yandextank.plugins.Aggregator import AggregatorPlugin
from yandextank.plugins.Autostop import AutostopPlugin, AbstractCriteria
from yandextank.plugins.Console import \
    ConsolePlugin, AbstractInfoWidget
from utils import PhantomConfig
from reader import PhantomReader
from yandextank.core import AbstractPlugin
import yandextank.core as tankcore


class PhantomPlugin(AbstractPlugin):
    """     Plugin for running phantom tool    """

    OPTION_CONFIG = "config"
    SECTION = PhantomConfig.SECTION

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.config = None
        self.process = None

        self.predefined_phout = None
        self.phout_import_mode = False
        self.did_phout_import_try = False

        self.phantom_path = None
        self.eta_file = None
        self.processed_ammo_count = 0
        self.phantom_start_time = time.time()
        self.buffered_seconds = "2"

        self.taskset_affinity = None
        self.cpu_count = mp.cpu_count()

        self.phantom = None
        self.cached_info = None
        self.phantom_stderr = None

        self.enum_ammo = False

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        opts = ["eta_file", "phantom_path", "buffered_seconds",
                "exclude_markers"]
        opts += 'affinity'
        opts += [PhantomConfig.OPTION_PHOUT, self.OPTION_CONFIG]
        opts += PhantomConfig.get_available_options()
        return opts

    def configure(self):
        # plugin part
        self.config = self.get_option(self.OPTION_CONFIG, '')
        self.eta_file = self.get_option("eta_file", '')
        self.core.add_artifact_file(self.eta_file)
        self.phantom_path = self.get_option("phantom_path", 'phantom')
        self.enum_ammo = self.get_option("enum_ammo", False)
        self.buffered_seconds = int(self.get_option("buffered_seconds",
                                                    self.buffered_seconds))
        self.exclude_markers = set(filter(
            (lambda marker: marker != ''), self.get_option('exclude_markers',
                                                           []).split(' ')))
        self.taskset_affinity = self.get_option('affinity', '')

        try:
            autostop = self.core.get_plugin_of_type(AutostopPlugin)
            autostop.add_criteria_class(UsedInstancesCriteria)
        except KeyError:
            self.log.debug(
                "No autostop plugin found, not adding instances criteria")

        self.predefined_phout = self.get_option(PhantomConfig.OPTION_PHOUT, '')
        if not self.get_option(self.OPTION_CONFIG,
                               '') and self.predefined_phout:
            self.phout_import_mode = True

        if not self.config and not self.phout_import_mode:
            self.phantom = PhantomConfig(self.core)
            self.phantom.read_config()

    def prepare_test(self):
        aggregator = None
        try:
            aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        except Exception, ex:
            self.log.warning("No aggregator found: %s", ex)

        if not self.config and not self.phout_import_mode:

            # generate config
            self.config = self.phantom.compose_config()
            args = [self.phantom_path, 'check', self.config]

            try:
                result = tankcore.execute(args, catch_out=True)
            except OSError:
                raise RuntimeError("Phantom I/O engine is not installed!")

            retcode = result[0]
            if retcode:
                raise RuntimeError(
                    "Config check failed. Subprocess returned code %s" %
                    retcode)
            if result[2]:
                raise RuntimeError("Subprocess returned message: %s" %
                                   result[2])
            reader = PhantomReader(self.phantom.phout_file)
        else:
            reader = PhantomReader(self.predefined_phout)
        if aggregator:
            aggregator.reader = reader
        try:
            console = self.core.get_plugin_of_type(ConsolePlugin)
        except Exception, ex:
            self.log.debug("Console not found: %s", ex)
            console = None

        if console:
            if not self.phout_import_mode:
                widget = PhantomProgressBarWidget(self)
                if self.eta_file:
                    widget.eta_file = self.eta_file
                console.add_info_widget(widget)
                aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
                aggregator.add_result_listener(widget)

            widget = PhantomInfoWidget(self)
            console.add_info_widget(widget)
            aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
            aggregator.add_result_listener(widget)

    def start_test(self):
        if not self.phout_import_mode:
            args = [self.phantom_path, 'run', self.config]
            self.log.debug("Starting %s with arguments: %s", self.phantom_path,
                           args)
            if self.taskset_affinity != '':
                args = [self.core.taskset_path, '-c', self.taskset_affinity
                        ] + args
                self.log.debug(
                    'Enabling taskset for phantom with affinity: %s, cores count: %d',
                    self.taskset_affinity, self.cpu_count)
            self.phantom_start_time = time.time()
            phantom_stderr_file = self.core.mkstemp(".log",
                                                    "phantom_stdout_stderr_")
            self.core.add_artifact_file(phantom_stderr_file)
            self.phantom_stderr = open(phantom_stderr_file, 'w')
            self.process = subprocess.Popen(args,
                                            stderr=self.phantom_stderr,
                                            stdout=self.phantom_stderr,
                                            close_fds=True)
        else:
            if not os.path.exists(self.predefined_phout):
                raise RuntimeError("Phout file not exists for import: %s" %
                                   self.predefined_phout)
            self.log.warn(
                "Will import phout file instead of running phantom: %s",
                self.predefined_phout)

    def is_test_finished(self):
        if not self.phout_import_mode:
            retcode = self.process.poll()
            if retcode is not None:
                self.log.info("Phantom done its work with exit code: %s",
                              retcode)
                return abs(retcode)
            else:
                info = self.get_info()
                if info:
                    eta = int(info.duration) - (int(time.time()) -
                                                int(self.phantom_start_time))
                    self.publish('eta', eta)
                return -1
        else:
            if not self.processed_ammo_count or self.did_phout_import_try != self.processed_ammo_count:
                self.did_phout_import_try = self.processed_ammo_count
                return -1
            else:
                return 0

    def end_test(self, retcode):
        if self.process and self.process.poll() is None:
            self.log.warn("Terminating phantom process with PID %s",
                          self.process.pid)
            self.process.terminate()
            if self.process:
                self.process.communicate()
        else:
            self.log.debug("Seems phantom finished OK")
        if self.phantom_stderr:
            self.phantom_stderr.close()
        return retcode

    def post_process(self, retcode):
        if not retcode:
            info = self.get_info()
            if info and info.ammo_count != self.processed_ammo_count:
                self.log.warning(
                    "Planned ammo count %s differs from processed %s",
                    info.ammo_count, self.processed_ammo_count)
        return retcode

    def aggregate_second(self, second_aggregate_data):
        self.processed_ammo_count += second_aggregate_data.overall.RPS
        self.log.debug("Processed ammo count: %s/", self.processed_ammo_count)

    def get_info(self):
        """ returns info object """
        if not self.cached_info:
            if not self.phantom:
                return None
            self.cached_info = self.phantom.get_info()
        return self.cached_info


class PhantomProgressBarWidget(AbstractInfoWidget):
    """
    Widget that displays progressbar
    """

    def get_index(self):
        return 0

    def __init__(self, sender):
        AbstractInfoWidget.__init__(self)
        self.krutilka = ConsoleScreen.krutilka()
        self.owner = sender
        self.ammo_progress = 0
        self.eta_file = None

        info = self.owner.get_info()
        if info:
            self.ammo_count = int(info.ammo_count)
            self.test_duration = int(info.duration)
        else:
            self.ammo_count = 1
            self.test_duration = 1

    def render(self, screen):
        res = ""

        dur_seconds = int(time.time()) - int(self.owner.phantom_start_time)

        eta_time = 'N/A'
        eta_secs = -1
        progress = 0
        color_bg = screen.markup.BG_CYAN
        color_fg = screen.markup.CYAN
        if self.test_duration and self.test_duration >= dur_seconds:
            color_bg = screen.markup.BG_GREEN
            color_fg = screen.markup.GREEN
            eta_secs = self.test_duration - dur_seconds
            eta_time = datetime.timedelta(seconds=eta_secs)
            progress = float(dur_seconds) / self.test_duration
        elif self.ammo_progress:
            left_part = self.ammo_count - self.ammo_progress
            if left_part > 0:
                eta_secs = int(float(dur_seconds) / float(self.ammo_progress) *
                               float(left_part))
            else:
                eta_secs = 0
            eta_time = datetime.timedelta(seconds=eta_secs)
            if self.ammo_progress < self.ammo_count:
                progress = float(self.ammo_progress) / float(self.ammo_count)
            else:
                progress = 0.5

        if self.eta_file:
            handle = open(self.eta_file, 'w')
            handle.write(str(eta_secs))
            handle.close()

        perc = float(int(1000 * progress)) / 10
        str_perc = str(perc) + "%"

        pb_width = screen.right_panel_width - 1 - len(str_perc)

        progress_chars = '=' * (int(pb_width * progress) - 1)
        progress_chars += self.krutilka.next()

        res += color_bg + progress_chars + screen.markup.RESET + color_fg
        res += '~' * (pb_width - int(pb_width *
                                     progress)) + screen.markup.RESET + ' '
        res += str_perc + "\n"

        eta = 'ETA: %s' % eta_time
        dur = 'Duration: %s' % str(datetime.timedelta(seconds=dur_seconds))
        spaces = ' ' * (screen.right_panel_width - len(eta) - len(dur) - 1)
        res += dur + ' ' + spaces + eta

        return res

    # TODO
    def aggregate_second(self, second_aggregate_data):
        self.ammo_progress += second_aggregate_data.overall.RPS


class PhantomInfoWidget(AbstractInfoWidget):
    """
    Widget with information about current run state
    """

    def get_index(self):
        return 2

    def __init__(self, sender):
        AbstractInfoWidget.__init__(self)
        self.owner = sender
        self.instances = 0
        self.planned = 0
        self.RPS = 0
        self.selfload = 0
        self.time_lag = 0
        self.planned_rps_duration = 0

        info = self.owner.get_info()
        if info:
            self.instances_limit = int(info.instances)
            self.ammo_count = int(info.ammo_count)
        else:
            self.instances_limit = 1
            self.ammo_count = 1

    def render(self, screen):
        res = ''
        info = self.owner.get_info()
        if self.owner.phantom:
            template = "Hosts: %s => %s:%s\n Ammo: %s\nCount: %s\n Load: %s"
            data = (socket.gethostname(), info.address, info.port,
                    os.path.basename(info.ammo_file), self.ammo_count,
                    ' '.join(info.rps_schedule))
            res = template % data

            res += "\n\n"

        res += "Active instances: "
        if float(self.instances) / self.instances_limit > 0.8:
            res += screen.markup.RED + str(
                self.instances) + screen.markup.RESET
        elif float(self.instances) / self.instances_limit > 0.5:
            res += screen.markup.YELLOW + str(
                self.instances) + screen.markup.RESET
        else:
            res += str(self.instances)

        res += "\nPlanned requests: %s for %s\nActual responses: " % (
            self.planned,
            datetime.timedelta(seconds=self.planned_rps_duration))
        if not self.planned == self.RPS:
            res += screen.markup.YELLOW + str(self.RPS) + screen.markup.RESET
        else:
            res += str(self.RPS)

        res += "\n        Accuracy: "
        if self.selfload < 80:
            res += screen.markup.RED + ('%.2f' %
                                        self.selfload) + screen.markup.RESET
        elif self.selfload < 95:
            res += screen.markup.YELLOW + ('%.2f' %
                                           self.selfload) + screen.markup.RESET
        else:
            res += ('%.2f' % self.selfload)

        res += "%\n        Time lag: "
        if self.time_lag > self.owner.buffered_seconds * 5:
            self.log.debug("Time lag: %s", self.time_lag)
            res += screen.markup.RED + str(datetime.timedelta(
                seconds=self.time_lag)) + screen.markup.RESET
        elif self.time_lag > self.owner.buffered_seconds:
            res += screen.markup.YELLOW + str(datetime.timedelta(
                seconds=self.time_lag)) + screen.markup.RESET
        else:
            res += str(datetime.timedelta(seconds=self.time_lag))

        return res

    # TODO
    def aggregate_second(self, second_aggregate_data):
        self.instances = second_aggregate_data.overall.active_threads
        if self.planned == second_aggregate_data.overall.planned_requests:
            self.planned_rps_duration += 1
        else:
            self.planned = second_aggregate_data.overall.planned_requests
            self.planned_rps_duration = 1

        self.RPS = second_aggregate_data.overall.RPS
        self.selfload = second_aggregate_data.overall.selfload
        self.time_lag = int(time.time() - time.mktime(
            second_aggregate_data.time.timetuple()))


class UsedInstancesCriteria(AbstractCriteria):
    """
    Autostop criteria, based on active instances count
    """
    RC_INST = 24

    @staticmethod
    def get_type_string():
        return 'instances'

    def __init__(self, autostop, param_str):
        AbstractCriteria.__init__(self)
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
        self.seconds_limit = tankcore.expand_to_seconds(param_str.split(',')[
            1])

        try:
            phantom = autostop.core.get_plugin_of_type(PhantomPlugin)
            info = phantom.get_info()
            if info:
                self.threads_limit = info.instances
            if not self.threads_limit:
                raise ValueError(
                    "Cannot create 'instances' criteria with zero instances limit")
        except KeyError:
            self.log.warning(
                "No phantom module, 'instances' autostop disabled")

    def notify(self, aggregate_second):
        threads = aggregate_second.overall.active_threads
        if self.is_relative:
            threads = float(threads) / self.threads_limit
        if threads > self.level:
            if not self.seconds_count:
                self.cause_second = aggregate_second

            self.log.debug(self.explain())

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
        items = (self.get_level_str(), self.seconds_count,
                 self.cause_second.time)
        return "Testing threads (instances) utilization higher than %s for %ss, since %s" % items

    def widget_explain(self):
        items = (self.get_level_str(), self.seconds_count, self.seconds_limit)
        return "Instances >%s for %s/%ss" % items, float(
            self.seconds_count) / self.seconds_limit

# ========================================================================
