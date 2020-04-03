import datetime

from ...common.interfaces import AbstractInfoWidget


class BfgInfoWidget(AbstractInfoWidget):
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

    def on_aggregated_data(self, data, stat):
        self.instances = stat["metrics"]["instances"]

        self.RPS = data["overall"]["interval_real"]["len"]
        self.selfload = 0  # TODO
        self.time_lag = 0  # TODO

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
