""" Autostop facility """
# pylint: disable=C0301
import logging
import os.path

from . import criterions as cr
from . import cumulative_criterions as cum_cr
from ..Console import Plugin as ConsolePlugin
from ...common.interfaces import AbstractPlugin, AggregateResultListener, AbstractInfoWidget

logger = logging.getLogger(__name__)


class Plugin(AbstractPlugin, AggregateResultListener):
    """ Plugin that accepts criterion classes and triggers autostop """
    SECTION = 'autostop'

    def __init__(self, core, cfg, name):
        AbstractPlugin.__init__(self, core, cfg, name)
        AggregateResultListener.__init__(self)

        self.cause_criterion = None
        self.imbalance_rps = 0
        self._criterions = {}
        self.custom_criterions = []
        self.counting = []
        self._stop_report_path = ''

    @staticmethod
    def get_key():
        return __file__

    def get_counting(self):
        """ get criterions that are activated """
        return self.counting

    def add_counting(self, obj):
        """ add criterion that activated """
        self.counting += [obj]

    def add_criterion_class(self, criterion_class):
        """ add new criterion class """
        self.custom_criterions += [criterion_class]

    def get_available_options(self):
        return ["autostop", "report_file"]

    def configure(self):
        aggregator = self.core.job.aggregator
        aggregator.add_result_listener(self)

        self._stop_report_path = os.path.join(
            self.core.artifacts_dir,
            self.get_option("report_file", 'autostop_report.txt'))

        self.add_criterion_class(cr.AvgTimeCriterion)
        self.add_criterion_class(cr.NetCodesCriterion)
        self.add_criterion_class(cr.HTTPCodesCriterion)
        self.add_criterion_class(cr.QuantileCriterion)
        self.add_criterion_class(cr.SteadyCumulativeQuantilesCriterion)
        self.add_criterion_class(cr.TimeLimitCriterion)
        self.add_criterion_class(cum_cr.TotalFracTimeCriterion)
        self.add_criterion_class(cum_cr.TotalHTTPCodesCriterion)
        self.add_criterion_class(cum_cr.TotalNetCodesCriterion)
        self.add_criterion_class(cum_cr.TotalNegativeHTTPCodesCriterion)
        self.add_criterion_class(cum_cr.TotalNegativeNetCodesCriterion)
        self.add_criterion_class(cum_cr.TotalHTTPTrendCriterion)
        self.add_criterion_class(cum_cr.QuantileOfSaturationCriterion)

    def prepare_test(self):
        criterions = self.get_option("autostop")
        for criterion_str in criterions:
            if not criterion_str:
                continue
            self.log.debug("Criterion string: %s", criterion_str)
            self._criterions[criterion_str] = self.__create_criterion(
                criterion_str)

        self.log.debug("Criterion objects: %s", self._criterions)

        try:
            console = self.core.get_plugin_of_type(ConsolePlugin)
        except Exception as ex:  # pylint: disable=W0703
            self.log.debug("Console not found: %s", ex)
            console = None

        if console:
            console.add_info_widget(AutostopWidget(self))

    def is_test_finished(self):
        if self.cause_criterion:
            self.log.warning(
                "Autostop criterion requested test stop: %s",
                self.cause_criterion.explain())
            return self.cause_criterion.get_rc()
        else:
            return -1

    def __create_criterion(self, criterion_str):
        """ instantiate criterion from config string """
        parsed = criterion_str.split("(")
        type_str = parsed[0].strip().lower()
        parsed[1] = parsed[1].split(")")[0].strip()

        for criterion_class in self.custom_criterions:
            if criterion_class.get_type_string() == type_str:
                return criterion_class(self, parsed[1])
        raise ValueError(
            "Unsupported autostop criterion type: %s" % criterion_str)

    def on_aggregated_data(self, data, stat):
        self.counting = []
        if not self.cause_criterion:
            for criterion_text, criterion in self._criterions.items():
                if criterion.notify(data, stat):
                    self.cause_criterion = criterion
                    if self.cause_criterion.cause_second:
                        self.imbalance_rps = int(self.cause_criterion.cause_second[1]["metrics"]["reqps"])
                        if not self.imbalance_rps:
                            self.imbalance_rps = int(
                                self.cause_criterion.cause_second[0]["overall"]["interval_real"]["len"])
                    self.core.publish('autostop', 'rps', self.imbalance_rps)
                    self.core.publish('autostop', 'reason', criterion.explain())
                    self.log.warning(
                        "Autostop criterion requested test stop on %d rps: %s", self.imbalance_rps, criterion_text)
                    open(self._stop_report_path, 'w').write(criterion_text)
                    self.core.add_artifact_file(self._stop_report_path)


class AutostopWidget(AbstractInfoWidget):
    """ widget that displays counting criterions """

    def __init__(self, sender):
        AbstractInfoWidget.__init__(self)
        self.owner = sender

    def get_index(self):
        return 25

    def render(self, screen):
        res = []
        candidates = self.owner.get_counting()
        for candidate in candidates:
            text, perc = candidate.widget_explain()
            if perc >= 0.95:
                res += [screen.markup.RED_DARK + text + screen.markup.RESET]
            elif perc >= 0.8:
                res += [screen.markup.RED + text + screen.markup.RESET]
            elif perc >= 0.5:
                res += [screen.markup.YELLOW + text + screen.markup.RESET]
            else:
                res += [text]

        if res:
            return "Autostop:\n  " + ("\n  ".join(res))
        else:
            return ''
