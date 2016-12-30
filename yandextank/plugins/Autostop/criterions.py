import copy
import json
import logging
import re
import time

from yandextank.common.util import expand_to_seconds, expand_to_milliseconds
from ...common.interfaces import AbstractCriterion

logger = logging.getLogger(__name__)


class AvgTimeCriterion(AbstractCriterion):
    """ average response time criterion """

    @staticmethod
    def get_type_string():
        return 'time'

    def __init__(self, autostop, param_str):
        AbstractCriterion.__init__(self)
        self.seconds_count = 0
        self.rt_limit = expand_to_milliseconds(param_str.split(',')[0])
        self.seconds_limit = expand_to_seconds(param_str.split(',')[1])
        self.autostop = autostop

    def notify(self, data, stat):
        if (
                data["overall"]["interval_real"]["total"] / 1000.0 /
                data["overall"]["interval_real"]["len"]) > self.rt_limit:
            if not self.seconds_count:
                self.cause_second = (data, stat)

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
        explanation = (
            "Average response time higher"
            " than %sms for %ss, since %s" %
            (self.rt_limit, self.seconds_count, self.cause_second[0]["ts"]))
        return explanation

    def widget_explain(self):
        items = (self.rt_limit, self.seconds_count, self.seconds_limit)
        return "Avg Time >%sms for %s/%ss" % items, float(
            self.seconds_count) / self.seconds_limit


class HTTPCodesCriterion(AbstractCriterion):
    """ HTTP codes criterion """

    @staticmethod
    def get_type_string():
        return 'http'

    def __init__(self, autostop, param_str):
        AbstractCriterion.__init__(self)
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
        self.seconds_limit = expand_to_seconds(param_str.split(',')[2])

    def notify(self, data, stat):
        matched_responses = self.count_matched_codes(
            self.codes_regex, data["overall"]["proto_code"]["count"])
        if self.is_relative:
            if data["overall"]["interval_real"]["len"]:
                matched_responses = float(matched_responses) / data["overall"][
                    "interval_real"]["len"]
            else:
                matched_responses = 0
        logger.debug(
            "HTTP codes matching mask %s: %s/%s", self.codes_mask,
            matched_responses, self.level)

        if matched_responses >= self.level:
            if not self.seconds_count:
                self.cause_second = (data, stat)

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
        items = (
            self.codes_mask, self.get_level_str(), self.seconds_count,
            self.cause_second[0].get('ts'))
        return "%s codes count higher than %s for %ss, since %s" % items

    def widget_explain(self):
        items = (
            self.codes_mask, self.get_level_str(), self.seconds_count,
            self.seconds_limit)
        return "HTTP %s>%s for %s/%ss" % items, float(
            self.seconds_count) / self.seconds_limit


class NetCodesCriterion(AbstractCriterion):
    """ Net codes criterion """

    @staticmethod
    def get_type_string():
        return 'net'

    def __init__(self, autostop, param_str):
        AbstractCriterion.__init__(self)
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
        self.seconds_limit = expand_to_seconds(param_str.split(',')[2])

    def notify(self, data, stat):
        codes = copy.deepcopy(data["overall"]["net_code"]["count"])
        if '0' in codes.keys():
            codes.pop('0')
        matched_responses = self.count_matched_codes(self.codes_regex, codes)
        if self.is_relative:
            if data["overall"]["interval_real"]["len"]:
                matched_responses = float(matched_responses) / data["overall"][
                    "interval_real"]["len"]
            else:
                matched_responses = 0
        logger.debug(
            "Net codes matching mask %s: %s/%s", self.codes_mask,
            matched_responses, self.level)

        if matched_responses >= self.level:
            if not self.seconds_count:
                self.cause_second = (data, stat)

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
        items = (
            self.codes_mask, self.get_level_str(), self.seconds_count,
            self.cause_second[0].get("ts"))
        return "%s net codes count higher than %s for %ss, since %s" % items

    def widget_explain(self):
        items = (
            self.codes_mask, self.get_level_str(), self.seconds_count,
            self.seconds_limit)
        return "Net %s>%s for %s/%ss" % items, float(
            self.seconds_count) / self.seconds_limit


class QuantileCriterion(AbstractCriterion):
    """ quantile criterion """

    @staticmethod
    def get_type_string():
        return 'quantile'

    def __init__(self, autostop, param_str):
        AbstractCriterion.__init__(self)
        self.seconds_count = 0
        self.quantile = float(param_str.split(',')[0])
        self.rt_limit = expand_to_milliseconds(param_str.split(',')[1])
        self.seconds_limit = expand_to_seconds(param_str.split(',')[2])
        self.autostop = autostop

    def notify(self, data, stat):
        quantiles = dict(
            zip(
                data["overall"]["interval_real"]["q"]["q"], data["overall"][
                    "interval_real"]["q"]["value"]))
        if self.quantile not in quantiles.keys():
            logger.warning("No quantile %s in %s", self.quantile, quantiles)
        if self.quantile in quantiles.keys() \
                and quantiles[self.quantile] / 1000.0 > self.rt_limit:
            if not self.seconds_count:
                self.cause_second = (data, stat)

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
        items = (
            self.quantile, self.rt_limit, self.seconds_count,
            self.cause_second[0].get("ts"))
        return "Percentile %s higher than %sms for %ss, since %s" % items

    def widget_explain(self):
        items = (
            self.quantile, self.rt_limit, self.seconds_count,
            self.seconds_limit)
        return "%s%% >%sms for %s/%ss" % items, float(
            self.seconds_count) / self.seconds_limit


class SteadyCumulativeQuantilesCriterion(AbstractCriterion):
    """ quantile criterion """

    @staticmethod
    def get_type_string():
        return 'steady_cumulative'

    def __init__(self, autostop, param_str):
        raise NotImplementedError
        AbstractCriterion.__init__(self)
        self.seconds_count = 0
        self.quantile_hash = ""
        self.seconds_limit = expand_to_seconds(param_str.split(',')[0])
        self.autostop = autostop

    def notify(self, data, stat):
        quantiles = dict(
            zip(data["overall"]["q"]["q"], data["overall"]["q"]["values"]))
        quantile_hash = json.dumps(quantiles)
        logging.debug("Cumulative quantiles hash: %s", quantile_hash)
        if self.quantile_hash == quantile_hash:
            if not self.seconds_count:
                self.cause_second = (data, stat)

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
        items = (self.seconds_count, self.cause_second[0]["ts"])
        return "Cumulative percentiles are steady for %ss, since %s" % items

    def widget_explain(self):
        items = (self.seconds_count, self.seconds_limit)
        return "Steady for %s/%ss" % items, float(
            self.seconds_count) / self.seconds_limit


class TimeLimitCriterion(AbstractCriterion):
    """ time limit criterion """

    @staticmethod
    def get_type_string():
        return 'limit'

    def __init__(self, autostop, param_str):
        AbstractCriterion.__init__(self)
        self.start_time = time.time()
        self.end_time = time.time()
        self.time_limit = expand_to_seconds(param_str)

    def notify(self, data, stat):
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
