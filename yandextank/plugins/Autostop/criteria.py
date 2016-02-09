import yandextank.core as tankcore
import json
import re
import time
import copy
import logging

logger = logging.getLogger(__name__)


class AbstractCriteria(object):
    """ parent class for all criterias """
    RC_TIME = 21
    RC_HTTP = 22
    RC_NET = 23
    RC_STEADY = 33

    def __init__(self):
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
        self.rt_limit = tankcore.expand_to_milliseconds(param_str.split(',')[
            0])
        self.seconds_limit = tankcore.expand_to_seconds(param_str.split(',')[
            1])
        self.autostop = autostop

    def notify(self, aggregate_second):
        if aggregate_second.overall.avg_response_time > self.rt_limit:
            if not self.seconds_count:
                self.cause_second = aggregate_second

            logger.debug(self.explain())

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
        return "Avg Time >%sms for %s/%ss" % items, float(
            self.seconds_count) / self.seconds_limit


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
        self.seconds_limit = tankcore.expand_to_seconds(param_str.split(',')[
            2])

    def notify(self, aggregate_second):
        matched_responses = self.count_matched_codes(
            self.codes_regex, aggregate_second.overall.http_codes)
        if self.is_relative:
            if aggregate_second.overall.RPS:
                matched_responses = float(
                    matched_responses) / aggregate_second.overall.RPS
            else:
                matched_responses = 0
        logger.debug("HTTP codes matching mask %s: %s/%s", self.codes_mask,
                     matched_responses, self.level)

        if matched_responses >= self.level:
            if not self.seconds_count:
                self.cause_second = aggregate_second

            logger.debug(self.explain())

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
        items = (self.codes_mask, self.get_level_str(), self.seconds_count,
                 self.cause_second.time)
        return "%s codes count higher than %s for %ss, since %s" % items

    def widget_explain(self):
        items = (self.codes_mask, self.get_level_str(), self.seconds_count,
                 self.seconds_limit)
        return "HTTP %s>%s for %s/%ss" % items, float(
            self.seconds_count) / self.seconds_limit


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
        self.seconds_limit = tankcore.expand_to_seconds(param_str.split(',')[
            2])

    def notify(self, aggregate_second):
        codes = copy.deepcopy(aggregate_second.overall.net_codes)
        if '0' in codes.keys():
            codes.pop('0')
        matched_responses = self.count_matched_codes(self.codes_regex, codes)
        if self.is_relative:
            if aggregate_second.overall.RPS:
                matched_responses = float(
                    matched_responses) / aggregate_second.overall.RPS
            else:
                matched_responses = 0
        logger.debug("Net codes matching mask %s: %s/%s", self.codes_mask,
                     matched_responses, self.level)

        if matched_responses >= self.level:
            if not self.seconds_count:
                self.cause_second = aggregate_second

            logger.debug(self.explain())

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
        items = (self.codes_mask, self.get_level_str(), self.seconds_count,
                 self.cause_second.time)
        return "%s net codes count higher than %s for %ss, since %s" % items

    def widget_explain(self):
        items = (self.codes_mask, self.get_level_str(), self.seconds_count,
                 self.seconds_limit)
        return "Net %s>%s for %s/%ss" % items, float(
            self.seconds_count) / self.seconds_limit


class QuantileCriteria(AbstractCriteria):
    """ quantile criteria """

    @staticmethod
    def get_type_string():
        return 'quantile'

    def __init__(self, autostop, param_str):
        AbstractCriteria.__init__(self)
        self.seconds_count = 0
        self.quantile = float(param_str.split(',')[0])
        self.rt_limit = tankcore.expand_to_milliseconds(param_str.split(',')[
            1])
        self.seconds_limit = tankcore.expand_to_seconds(param_str.split(',')[
            2])
        self.autostop = autostop

    def notify(self, aggregate_second):
        if self.quantile not in aggregate_second.overall.quantiles.keys():
            logger.warning("No quantile %s in %s", self.quantile,
                           aggregate_second.overall.quantiles)
        if self.quantile in aggregate_second.overall.quantiles.keys() \
                and aggregate_second.overall.quantiles[self.quantile] > self.rt_limit:
            if not self.seconds_count:
                self.cause_second = aggregate_second

            logger.debug(self.explain())

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
        items = (self.quantile, self.rt_limit, self.seconds_count,
                 self.cause_second.time)
        return "Percentile %s higher than %sms for %ss, since %s" % items

    def widget_explain(self):
        items = (self.quantile, self.rt_limit, self.seconds_count,
                 self.seconds_limit)
        return "%s%% >%sms for %s/%ss" % items, float(
            self.seconds_count) / self.seconds_limit


class SteadyCumulativeQuantilesCriteria(AbstractCriteria):
    """ quantile criteria """

    @staticmethod
    def get_type_string():
        return 'steady_cumulative'

    def __init__(self, autostop, param_str):
        AbstractCriteria.__init__(self)
        self.seconds_count = 0
        self.quantile_hash = ""
        self.seconds_limit = tankcore.expand_to_seconds(param_str.split(',')[
            0])
        self.autostop = autostop

    def notify(self, aggregate_second):
        quantile_hash = json.dumps(aggregate_second.cumulative.quantiles)
        logging.debug("Cumulative quantiles hash: %s", quantile_hash)
        if self.quantile_hash == quantile_hash:
            if not self.seconds_count:
                self.cause_second = aggregate_second

            logger.debug(self.explain())

            self.seconds_count += 1
            self.autostop.add_counting(self)
            if self.seconds_count >= self.seconds_limit:
                return True
        else:
            self.seconds_count = 0

        self.quantile_hash = quantile_hash
        return False

    def get_rc(self):
        return self.RC_STEADY

    def explain(self):
        items = (self.seconds_count, self.cause_second.time)
        return "Cumulative percentiles are steady for %ss, since %s" % items

    def widget_explain(self):
        items = (self.seconds_count, self.seconds_limit)
        return "Steady for %s/%ss" % items, float(
            self.seconds_count) / self.seconds_limit


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
        return "Test time elapsed. Limit: %ss, actual time: %ss" % (
            self.time_limit, self.end_time - self.start_time)

    def widget_explain(self):
        return "Time limit: %ss, actual time: %ss" % (
            self.time_limit, self.end_time - self.start_time)
