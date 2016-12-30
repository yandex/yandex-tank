import datetime
import logging
import os
import socket
import time

from ...common.interfaces import AbstractInfoWidget

from ..Console import screen

logger = logging.getLogger(__name__)


class PhantomProgressBarWidget(AbstractInfoWidget):
    """
    Widget that displays progressbar
    """

    def get_index(self):
        return 0

    def __init__(self, sender):
        AbstractInfoWidget.__init__(self)
        self.krutilka = screen.krutilka()
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
                eta_secs = int(
                    float(dur_seconds) / float(self.ammo_progress) *
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
        res += '~' * (pb_width - int(pb_width * progress)
                      ) + screen.markup.RESET + ' '
        res += str_perc + "\n"

        eta = 'ETA: %s' % eta_time
        dur = 'Duration: %s' % str(datetime.timedelta(seconds=dur_seconds))
        spaces = ' ' * (screen.right_panel_width - len(eta) - len(dur) - 1)
        res += dur + ' ' + spaces + eta

        return res

    def on_aggregated_data(self, data, stats):
        self.ammo_progress += data["overall"]["interval_real"]["len"]


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
            data = (
                socket.gethostname(), info.address, info.port,
                os.path.basename(info.ammo_file), self.ammo_count,
                ' '.join(info.rps_schedule))
            res = template % data

            res += "\n\n"

        res += "Active instances: "
        if float(self.instances) / self.instances_limit > 0.8:
            res += screen.markup.RED + str(self.instances) + screen.markup.RESET
        elif float(self.instances) / self.instances_limit > 0.5:
            res += screen.markup.YELLOW + str(
                self.instances) + screen.markup.RESET
        else:
            res += str(self.instances)

        res += "\nPlanned requests: %s for %s\nActual responses: " % (
            self.planned, datetime.timedelta(seconds=self.planned_rps_duration))
        if not self.planned == self.RPS:
            res += screen.markup.YELLOW + str(self.RPS) + screen.markup.RESET
        else:
            res += str(self.RPS)

        res += "\n        Accuracy: "
        if self.selfload < 80:
            res += screen.markup.RED + (
                '%.2f' % self.selfload) + screen.markup.RESET
        elif self.selfload < 95:
            res += screen.markup.YELLOW + (
                '%.2f' % self.selfload) + screen.markup.RESET
        else:
            res += ('%.2f' % self.selfload)

        res += "%\n        Time lag: "
        if self.time_lag > self.owner.buffered_seconds * 5:
            logger.debug("Time lag: %s", self.time_lag)
            res += screen.markup.RED + str(
                datetime.timedelta(seconds=self.time_lag)) + screen.markup.RESET
        elif self.time_lag > self.owner.buffered_seconds:
            res += screen.markup.YELLOW + str(
                datetime.timedelta(seconds=self.time_lag)) + screen.markup.RESET
        else:
            res += str(datetime.timedelta(seconds=self.time_lag))

        return res

    def on_aggregated_data(self, data, stats):
        self.RPS = data["overall"]["interval_real"]["len"]
        self.planned = stats["metrics"]["reqps"]
        self.instances = stats["metrics"]["instances"]


#           TODO:
#           self.selfload = second_aggregate_data.overall.selfload
#           self.time_lag = int(time.time() - time.mktime(
#               second_aggregate_data.time.timetuple()))
