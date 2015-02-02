""" Autostop facility """
import copy
import logging
import re
import json

from Aggregator import AggregatorPlugin, AggregateResultListener
from ConsoleOnline import AbstractInfoWidget, ConsoleOnlinePlugin
from yandextank.core import AbstractPlugin
import yandextank.core as tankcore
import time


class AutostopPlugin(AbstractPlugin, AggregateResultListener):
    """ Plugin that accepts criteria classes and triggers autostop """
    SECTION = 'autostop'

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.cause_criteria = None
        self.criterias = []
        self.custom_criterias = []
        self.counting = []
        self.criteria_str = ''

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
        return ["autostop"]

    def configure(self):
        aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        aggregator.add_result_listener(self)
        self.criteria_str = " ".join(self.get_option("autostop", '').split("\n"))
        self.add_criteria_class(AvgTimeCriteria)
        self.add_criteria_class(NetCodesCriteria)
        self.add_criteria_class(HTTPCodesCriteria)
        self.add_criteria_class(QuantileCriteria)
        self.add_criteria_class(SteadyCumulativeQuantilesCriteria)
        self.add_criteria_class(TimeLimitCriteria)

    def prepare_test(self):
        for criteria_str in self.criteria_str.strip().split(")"):
            if not criteria_str:
                continue
            self.log.debug("Criteria string: %s", criteria_str)
            self.criterias.append(self.__create_criteria(criteria_str))

        self.log.debug("Criteria object: %s", self.criterias)

        try:
            console = self.core.get_plugin_of_type(ConsoleOnlinePlugin)
        except Exception, ex:
            self.log.debug("Console not found: %s", ex)
            console = None

        if console:
            console.add_info_widget(AutostopWidget(self))

    def is_test_finished(self):
        if self.cause_criteria:
            self.log.info("Autostop criteria requested test stop: %s", self.cause_criteria.explain())
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
        raise ValueError("Unsupported autostop criteria type: %s" % criteria_str)

    def aggregate_second(self, second_aggregate_data):
        self.counting = []
        if not self.cause_criteria:
            for criteria in self.criterias:
                if criteria.notify(second_aggregate_data):
                    self.log.debug("Autostop criteria requested test stop: %s", criteria)
                    self.cause_criteria = criteria


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


class AbstractCriteria:
    """ parent class for all criterias """
    RC_TIME = 21
    RC_HTTP = 22
    RC_NET = 23
    RC_STEADY = 33

    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.cause_second = None

    @staticmethod
    def count_matched_codes(codes_regex, codes_dict):
        """ helper to aggregate codes by mask """
        total = 0
        for code, count in codes_dict.items():
            if codes_regex.match(str(code)):
                total += count
        return total

    def notify(self, aggregate_second):
        """ notification about aggregate data goes here """
        raise NotImplementedError("Abstract methods requires overriding")

    def get_rc(self):
        """ get return code for test """
        raise NotImplementedError("Abstract methods requires overriding")

    def explain(self):
        """ long explanation to show after test stop """
        raise NotImplementedError("Abstract methods requires overriding")

    def widget_explain(self):
        """ short explanation to display in right panel """
        return self.explain(), 0

    @staticmethod
    def get_type_string():
        """ returns string that used as config name for criteria """
        raise NotImplementedError("Abstract methods requires overriding")


class AvgTimeCriteria(AbstractCriteria):
    """ average response time criteria """

    @staticmethod
    def get_type_string():
        return 'time'

    def __init__(self, autostop, param_str):
        AbstractCriteria.__init__(self)
        self.seconds_count = 0
        self.rt_limit = tankcore.expand_to_milliseconds(param_str.split(',')[0])
        self.seconds_limit = tankcore.expand_to_seconds(param_str.split(',')[1])
        self.autostop = autostop

    def notify(self, aggregate_second):
        if aggregate_second.overall.avg_response_time > self.rt_limit:
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
        return self.RC_TIME

    def explain(self):
        items = (self.rt_limit, self.seconds_count, self.cause_second.time)
        return "Average response time higher than %sms for %ss, since %s" % items

    def widget_explain(self):
        items = (self.rt_limit, self.seconds_count, self.seconds_limit)
        return "Avg Time >%sms for %s/%ss" % items, float(self.seconds_count) / self.seconds_limit


class HTTPCodesCriteria(AbstractCriteria):
    """ HTTP codes criteria """

    @staticmethod
    def get_type_string():
        return 'http'

    def __init__(self, autostop, param_str):
        AbstractCriteria.__init__(self)
        self.seconds_count = 0
        self.codes_mask = param_str.split(',')[0].lower()
        self.codes_regex = re.compile(self.codes_mask.replace("x", '.'))
        self.autostop = autostop

        level_str = param_str.split(',')[1].strip()
        if level_str[-1:] == '%':
            self.level = float(level_str[:-1]) / 100
            self.is_relative = True
        else:
            self.level = int(level_str)
            self.is_relative = False
        self.seconds_limit = tankcore.expand_to_seconds(param_str.split(',')[2])


    def notify(self, aggregate_second):
        matched_responses = self.count_matched_codes(self.codes_regex, aggregate_second.overall.http_codes)
        if self.is_relative:
            if aggregate_second.overall.RPS:
                matched_responses = float(matched_responses) / aggregate_second.overall.RPS
            else:
                matched_responses = 0
        self.log.debug("HTTP codes matching mask %s: %s/%s", self.codes_mask, matched_responses, self.level)

        if matched_responses >= self.level:
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
        return self.RC_HTTP

    def get_level_str(self):
        """ format level str """
        if self.is_relative:
            level_str = str(100 * self.level) + "%"
        else:
            level_str = self.level
        return level_str

    def explain(self):
        items = (self.codes_mask, self.get_level_str(), self.seconds_count, self.cause_second.time)
        return "%s codes count higher than %s for %ss, since %s" % items

    def widget_explain(self):
        items = (self.codes_mask, self.get_level_str(), self.seconds_count, self.seconds_limit)
        return "HTTP %s>%s for %s/%ss" % items, float(self.seconds_count) / self.seconds_limit


class NetCodesCriteria(AbstractCriteria):
    """ Net codes criteria """

    @staticmethod
    def get_type_string():
        return 'net'

    def __init__(self, autostop, param_str):
        AbstractCriteria.__init__(self)
        self.seconds_count = 0
        self.codes_mask = param_str.split(',')[0].lower()
        self.codes_regex = re.compile(self.codes_mask.replace("x", '.'))
        self.autostop = autostop

        level_str = param_str.split(',')[1].strip()
        if level_str[-1:] == '%':
            self.level = float(level_str[:-1]) / 100
            self.is_relative = True
        else:
            self.level = int(level_str)
            self.is_relative = False
        self.seconds_limit = tankcore.expand_to_seconds(param_str.split(',')[2])


    def notify(self, aggregate_second):
        codes = copy.deepcopy(aggregate_second.overall.net_codes)
        if '0' in codes.keys():
            codes.pop('0')
        matched_responses = self.count_matched_codes(self.codes_regex, codes)
        if self.is_relative:
            if aggregate_second.overall.RPS:
                matched_responses = float(matched_responses) / aggregate_second.overall.RPS
            else:
                matched_responses = 0
        self.log.debug("Net codes matching mask %s: %s/%s", self.codes_mask, matched_responses, self.level)

        if matched_responses >= self.level:
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
        return self.RC_NET

    def get_level_str(self):
        """ format level str """
        if self.is_relative:
            level_str = str(100 * self.level) + "%"
        else:
            level_str = self.level
        return level_str

    def explain(self):
        items = (self.codes_mask, self.get_level_str(), self.seconds_count, self.cause_second.time)
        return "%s net codes count higher than %s for %ss, since %s" % items

    def widget_explain(self):
        items = (self.codes_mask, self.get_level_str(), self.seconds_count, self.seconds_limit)
        return "Net %s>%s for %s/%ss" % items, float(self.seconds_count) / self.seconds_limit


class QuantileCriteria(AbstractCriteria):
    """ quantile criteria """

    @staticmethod
    def get_type_string():
        return 'quantile'

    def __init__(self, autostop, param_str):
        AbstractCriteria.__init__(self)
        self.seconds_count = 0
        self.quantile = float(param_str.split(',')[0])
        self.rt_limit = tankcore.expand_to_milliseconds(param_str.split(',')[1])
        self.seconds_limit = tankcore.expand_to_seconds(param_str.split(',')[2])
        self.autostop = autostop

    def notify(self, aggregate_second):
        if not (self.quantile in aggregate_second.overall.quantiles.keys()):
            self.log.warning("No quantile %s in %s", self.quantile, aggregate_second.overall.quantiles)
        if self.quantile in aggregate_second.overall.quantiles.keys() \
                and aggregate_second.overall.quantiles[self.quantile] > self.rt_limit:
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
        return self.RC_TIME

    def explain(self):
        items = (self.quantile, self.rt_limit, self.seconds_count, self.cause_second.time)
        return "Percentile %s higher than %sms for %ss, since %s" % items

    def widget_explain(self):
        items = (self.quantile, self.rt_limit, self.seconds_count, self.seconds_limit)
        return "%s%% >%sms for %s/%ss" % items, float(self.seconds_count) / self.seconds_limit


class SteadyCumulativeQuantilesCriteria(AbstractCriteria):
    """ quantile criteria """

    @staticmethod
    def get_type_string():
        return 'steady_cumulative'

    def __init__(self, autostop, param_str):
        AbstractCriteria.__init__(self)
        self.seconds_count = 0
        self.hash = ""
        self.seconds_limit = tankcore.expand_to_seconds(param_str.split(',')[0])
        self.autostop = autostop

    def notify(self, aggregate_second):
        hash = json.dumps(aggregate_second.cumulative.quantiles)
        logging.debug("Cumulative quantiles hash: %s", hash)
        if self.hash == hash:
            if not self.seconds_count:
                self.cause_second = aggregate_second

            self.log.debug(self.explain())

            self.seconds_count += 1
            self.autostop.add_counting(self)
            if self.seconds_count >= self.seconds_limit:
                return True
        else:
            self.seconds_count = 0

        self.hash = hash
        return False

    def get_rc(self):
        return self.RC_STEADY

    def explain(self):
        items = (self.seconds_count, self.cause_second.time)
        return "Cumulative percentiles are steady for %ss, since %s" % items

    def widget_explain(self):
        items = (self.seconds_count, self.seconds_limit)
        return "Steady for %s/%ss" % items, float(self.seconds_count) / self.seconds_limit

class TimeLimitCriteria(AbstractCriteria):
    """ time limit criteria """

    @staticmethod
    def get_type_string():
        return 'limit'

    def __init__(self, autostop, param_str):
        AbstractCriteria.__init__(self)
        self.start_time = time.time()
        self.end_time = time.time()
        self.time_limit = tankcore.expand_to_seconds(param_str)

    def notify(self, aggregate_second):
        self.end_time = time.time()
        return (self.end_time - self.start_time) > self.time_limit


    def get_rc(self):
        return self.RC_TIME

    def explain(self):
        return "Test time elapsed. Limit: %ss, actual time: %ss" % (self.time_limit, self.end_time - self.start_time)

    def widget_explain(self):
        return "Time limit: %ss, actual time: %ss" % (self.time_limit, self.end_time - self.start_time)
