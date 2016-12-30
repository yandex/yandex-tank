""" Autostop facility """
# pylint: disable=C0301
import logging
import os.path

from ...common.interfaces import AbstractPlugin, AggregateResultListener, AbstractInfoWidget

from . import criterions as cr
from . import cumulative_criterions as cum_cr
from ..Aggregator import Plugin as AggregatorPlugin
from ..Console import Plugin as ConsolePlugin

logger = logging.getLogger(__name__)


class Plugin(AbstractPlugin, AggregateResultListener):
    """ Plugin that accepts criterion classes and triggers autostop """
    SECTION = 'autostop'

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        AggregateResultListener.__init__(self)

        self.cause_criterion = None
        self._criterions = {}
        self.custom_criterions = []
        self.counting = []
        self.criterion_str = ''
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
        aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        aggregator.add_result_listener(self)

        self.criterion_str = " ".join(
            self.get_option("autostop", '').split("\n"))
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
        for criterion_str in self.criterion_str.strip().split(")"):
            if not criterion_str:
                continue
            self.log.debug("Criterion string: %s", criterion_str)
            self._criterions[criterion_str + ')'] = self.__create_criterion(
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
            self.log.info(
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
            for criterion_text, criterion in self._criterions.iteritems():
                if criterion.notify(data, stat):
                    self.log.debug(
                        "Autostop criterion requested test stop: %s", criterion)
                    self.cause_criterion = criterion
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
