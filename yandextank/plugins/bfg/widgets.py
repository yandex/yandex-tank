import datetime
import time
from yandextank.plugins.ConsoleOnline import AbstractInfoWidget


class BFGInfoWidget(AbstractInfoWidget):

    ''' Console widget '''

    def __init__(self):
        AbstractInfoWidget.__init__(self)
        self.active_threads = 0
        self.instances = 0
        self.planned = 0
        self.RPS = 0
        self.selfload = 0
        self.time_lag = 0
        self.planned_rps_duration = 0

    def get_index(self):
        return 0

    def aggregate_second(self, second_aggregate_data):
        self.instances = second_aggregate_data.overall.active_threads
        if self.planned == second_aggregate_data.overall.planned_requests:
            self.planned_rps_duration += 1
        else:
            self.planned = second_aggregate_data.overall.planned_requests
            self.planned_rps_duration = 1

        self.RPS = second_aggregate_data.overall.RPS
        self.selfload = second_aggregate_data.overall.selfload
        self.time_lag = int(
            time.time() - time.mktime(second_aggregate_data.time.timetuple()))

    def render(self, screen):
        res = ''

        res += "Active instances: "
        res += str(self.instances)

        res += "\nPlanned requests: %s for %s\nActual responses: " % (
            self.planned, datetime.timedelta(seconds=self.planned_rps_duration))
        if not self.planned == self.RPS:
            res += screen.markup.YELLOW + str(self.RPS) + screen.markup.RESET
        else:
            res += str(self.RPS)

        res += "\n        Accuracy: "
        if self.selfload < 80:
            res += screen.markup.RED + \
                ('%.2f' % self.selfload) + screen.markup.RESET
        elif self.selfload < 95:
            res += screen.markup.YELLOW + \
                ('%.2f' % self.selfload) + screen.markup.RESET
        else:
            res += ('%.2f' % self.selfload)

        res += "%\n        Time lag: "
        res += str(datetime.timedelta(seconds=self.time_lag))

        return res
