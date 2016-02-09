""" Autostop facility """
# pylint: disable=C0301
import logging
import os.path

from yandextank.plugins.Aggregator import AggregatorPlugin, AggregateResultListener
from yandextank.plugins.Console import AbstractInfoWidget, ConsolePlugin
from yandextank.core import AbstractPlugin
import criteria as cr

logger = logging.getLogger(__name__)


class AutostopPlugin(AbstractPlugin, AggregateResultListener):
    """ Plugin that accepts criteria classes and triggers autostop """
    SECTION = 'autostop'

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        AggregateResultListener.__init__(self)

        self.cause_criteria = None
        self._criterias = {}
        self.custom_criterias = []
        self.counting = []
        self.criteria_str = ''
        self._stop_report_path = ''

    @staticmethod
    def get_key():
        return __file__

    def get_counting(self):
        """ get criterias that are activated """
        return self.counting

    def add_counting(self, obj):
        """ add criteria that activated """
        self.counting += [obj]

    def add_criteria_class(self, criteria_class):
        """ add new criteria class """
        self.custom_criterias += [criteria_class]

    def get_available_options(self):
        return ["autostop", "report_file"]

    def configure(self):
        aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        aggregator.add_result_listener(self)

        self.criteria_str = " ".join(self.get_option("autostop", '').split(
            "\n"))
        self._stop_report_path = os.path.join(
            self.core.artifacts_dir,
            self.get_option("report_file", 'autostop_report.txt'))

        self.add_criteria_class(cr.AvgTimeCriteria)
        self.add_criteria_class(cr.NetCodesCriteria)
        self.add_criteria_class(cr.HTTPCodesCriteria)
        self.add_criteria_class(cr.QuantileCriteria)
        self.add_criteria_class(cr.SteadyCumulativeQuantilesCriteria)
        self.add_criteria_class(cr.TimeLimitCriteria)

    def prepare_test(self):
        for criteria_str in self.criteria_str.strip().split(")"):
            if not criteria_str:
                continue
            self.log.debug("Criteria string: %s", criteria_str)
            self._criterias[criteria_str + ')'] = self.__create_criteria(
                criteria_str)

        self.log.debug("Criteria objects: %s", self._criterias)

        try:
            console = self.core.get_plugin_of_type(ConsolePlugin)
        except Exception, ex:  # pylint: disable=W0703
            self.log.debug("Console not found: %s", ex)
            console = None

        if console:
            console.add_info_widget(AutostopWidget(self))

    def is_test_finished(self):
        if self.cause_criteria:
            self.log.info("Autostop criteria requested test stop: %s",
                          self.cause_criteria.explain())
            return self.cause_criteria.get_rc()
        else:
            return -1

    def __create_criteria(self, criteria_str):
        """ instantiate criteria from config string """
        parsed = criteria_str.split("(")
        type_str = parsed[0].strip().lower()
        parsed[1] = parsed[1].split(")")[0].strip()

        for criteria_class in self.custom_criterias:
            if criteria_class.get_type_string() == type_str:
                return criteria_class(self, parsed[1])
        raise ValueError("Unsupported autostop criteria type: %s" %
                         criteria_str)

    def on_aggregated_data(self, data, stat):
        self.counting = []
        if not self.cause_criteria:
            for criteria_text, criteria in self._criterias.iteritems():
                if criteria.notify(data, stat):
                    self.log.debug("Autostop criteria requested test stop: %s",
                                   criteria)
                    self.cause_criteria = criteria
                    open(self._stop_report_path, 'w').write(criteria_text)
                    self.core.add_artifact_file(self._stop_report_path)


class AutostopWidget(AbstractInfoWidget):
    """ widget that displays counting criterias """

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
