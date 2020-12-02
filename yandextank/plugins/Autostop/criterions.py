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
        params = param_str.split(',')
        self.rt_limit = expand_to_milliseconds(params[0])
        self.seconds_limit = expand_to_seconds(params[1])
        self.autostop = autostop
        self.tag = params[2].strip() if len(params) == 3 else None

    def notify(self, data, stat):
        rt_total, requests_number = self.parse_data(data)
        rt_actual = rt_total / 1000.0 / requests_number

        if rt_actual > self.rt_limit:
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

    def parse_data(self, data):
        requests_number = data["overall"]["interval_real"]["len"]
        # Parse data for specific tag if it is present
        if self.tag:
            if data["tagged"].get(self.tag):
                rt_total = data["tagged"][self.tag]["interval_real"]["total"]
                requests_number = data["tagged"][self.tag]["interval_real"]["len"]
            # rt_total=0 if current tag differs from selected one
            else:
                rt_total = 0
        # Parse data for overall
        else:
            rt_total = data["overall"]["interval_real"]["total"]
        return rt_total, requests_number

    def get_rc(self):
        return self.RC_TIME

    def explain(self):
        items = self.get_criterion_parameters()
        explanation = "Average response time higher than %(limit)sms for %(seconds_count)ss, since %(since_time)s" % items
        if self.tag:
            explanation = explanation + " for tag %(tag)s" % items
        return explanation

    def get_criterion_parameters(self):
        parameters = {
            'limit': self.rt_limit,
            'seconds_count': self.seconds_count,
            'seconds_limit': self.seconds_limit,
            'since_time': self.cause_second[0]["ts"],
            'tag': self.tag
        }
        return parameters

    def widget_explain(self):
        items = self.get_criterion_parameters()
        return "Avg Time >%(limit)sms for %(seconds_count)s/%(seconds_limit)ss" % items, \
            float(self.seconds_count) / self.seconds_limit


class HTTPCodesCriterion(AbstractCriterion):
    """ HTTP codes criterion """

    @staticmethod
    def get_type_string():
        return 'http'

    def __init__(self, autostop, param_str):
        AbstractCriterion.__init__(self)
        self.seconds_count = 0
        params = param_str.split(',')
        self.codes_mask = params[0].lower()
        self.codes_regex = re.compile(self.codes_mask.replace("x", '.'))
        self.autostop = autostop

        level_str = params[1].strip()
        if level_str[-1:] == '%':
            self.level = float(level_str[:-1]) / 100
            self.is_relative = True
        else:
            self.level = int(level_str)
            self.is_relative = False
        self.seconds_limit = expand_to_seconds(params[2])
        self.tag = params[3].strip() if len(params) == 4 else None

    def notify(self, data, stat):
        matched_responses, total_responses = self.parse_data(data)
        if self.is_relative:
            if total_responses:
                matched_responses = float(matched_responses) / total_responses
            else:
                matched_responses = 0

        logger.debug("HTTP codes matching mask %s: %s/%s", self.codes_mask, matched_responses, self.level)

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

    def parse_data(self, data):
        # Parse data for specific tag
        if self.tag:
            if data["tagged"].get(self.tag):
                total_responses = data["tagged"][self.tag]["interval_real"]["len"]
                matched_responses = self.count_matched_codes(
                    self.codes_regex, data["tagged"][self.tag]["proto_code"]["count"])
            # matched_responses=0 if current tag differs from selected one
            else:
                matched_responses = 0
                total_responses = data["overall"]["interval_real"]["len"]
        # Parse data for overall
        else:
            matched_responses = self.count_matched_codes(self.codes_regex, data["overall"]["proto_code"]["count"])
            total_responses = data["overall"]["interval_real"]["len"]
        return matched_responses, total_responses

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
        items = self.get_criterion_parameters()
        explanation = "%(code)s codes count higher than %(level)s for %(seconds_count)ss, since %(since_time)s" % items
        if self.tag:
            explanation = explanation + " for tag %(tag)s" % items
        return explanation

    def get_criterion_parameters(self):
        parameters = {
            'code': self.codes_mask,
            'level': self.get_level_str(),
            'seconds_count': self.seconds_count,
            'seconds_limit': self.seconds_limit,
            'since_time': self.cause_second[0].get('ts'),
            'tag': self.tag
        }
        return parameters

    def widget_explain(self):
        items = self.get_criterion_parameters()
        return "HTTP %(code)s>%(level)s for %(seconds_count)s/%(seconds_limit)ss" % items, \
            float(self.seconds_count) / self.seconds_limit


class NetCodesCriterion(AbstractCriterion):
    """ Net codes criterion """

    @staticmethod
    def get_type_string():
        return 'net'

    def __init__(self, autostop, param_str):
        AbstractCriterion.__init__(self)
        self.seconds_count = 0
        params = param_str.split(',')
        self.codes_mask = params[0].lower()
        self.codes_regex = re.compile(self.codes_mask.replace("x", '.'))
        self.autostop = autostop

        level_str = params[1].strip()
        if level_str[-1:] == '%':
            self.level = float(level_str[:-1]) / 100
            self.is_relative = True
        else:
            self.level = int(level_str)
            self.is_relative = False
        self.seconds_limit = expand_to_seconds(params[2])
        self.tag = params[3].strip() if len(params) == 4 else None

    def notify(self, data, stat):
        matched_responses, total_responses = self.parse_data(data)
        if self.is_relative:
            if total_responses:
                matched_responses = float(matched_responses) / total_responses
            else:
                matched_responses = 0

        logger.debug("Net codes matching mask %s: %s/%s", self.codes_mask, matched_responses, self.level)

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

    def parse_data(self, data):
        # Count data for specific tag if it's present
        if self.tag:
            if data["tagged"].get(self.tag):
                total_responses = data["tagged"][self.tag]["interval_real"]["len"]
                code_count = data["tagged"][self.tag]["net_code"]["count"]
                codes = copy.deepcopy(code_count)
                if '0' in codes:
                    codes.pop('0')
                matched_responses = self.count_matched_codes(self.codes_regex, codes)
            # matched_responses=0 if current tag differs from selected one
            else:
                matched_responses = 0
                total_responses = data["overall"]["interval_real"]["len"]
        # Count data for overall
        else:
            code_count = data["overall"]["net_code"]["count"]
            total_responses = data["overall"]["interval_real"]["len"]
            codes = copy.deepcopy(code_count)
            if '0' in codes:
                codes.pop('0')
            matched_responses = self.count_matched_codes(self.codes_regex, codes)
        return matched_responses, total_responses

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
        items = self.get_criterion_parameters()
        explanation = "%(code)s net codes count higher than %(level)s for %(seconds_count)ss, since %(since_time)s" \
                      % items
        if self.tag:
            explanation = explanation + " for tag %(tag)s" % items
        return explanation

    def get_criterion_parameters(self):
        parameters = {
            'code': self.codes_mask,
            'level': self.get_level_str(),
            'seconds_count': self.seconds_count,
            'seconds_limit': self.seconds_limit,
            'since_time': self.cause_second[0].get("ts"),
            'tag': self.tag
        }
        return parameters

    def widget_explain(self):
        items = self.get_criterion_parameters()
        return "Net %(code)s>%(level)s for %(seconds_count)s/%(seconds_limit)ss" % items, \
            float(self.seconds_count) / self.seconds_limit


class QuantileCriterion(AbstractCriterion):
    """ quantile criterion """

    @staticmethod
    def get_type_string():
        return 'quantile'

    def __init__(self, autostop, param_str):
        AbstractCriterion.__init__(self)
        self.seconds_count = 0
        params = param_str.split(',')
        self.quantile = float(params[0])
        self.rt_limit = expand_to_milliseconds(params[1])
        self.seconds_limit = expand_to_seconds(params[2])
        self.autostop = autostop
        self.tag = params[3].strip() if len(params) == 4 else None

    def notify(self, data, stat):
        quantiles = self.parse_data(data)
        logger.debug('Autostop quantiles for ts %s: %s', data['ts'], quantiles)
        if self.quantile not in quantiles.keys():
            logger.warning("No quantile %s in %s", self.quantile, quantiles)
        if self.quantile in quantiles.keys() and quantiles[self.quantile] / 1000.0 > self.rt_limit:
            if not self.seconds_count:
                self.cause_second = (data, stat)

            self.seconds_count += 1
            logger.debug(self.explain())
            self.autostop.add_counting(self)
            if self.seconds_count >= self.seconds_limit:
                return True
        else:
            self.seconds_count = 0

        return False

    def parse_data(self, data):
        # Parse data for specific tag
        if self.tag:
            if data["tagged"].get(self.tag):
                quantile_values = data["tagged"][self.tag]["interval_real"]["q"]["value"]
            # quantile_values empty if current tag differs from selected one
            else:
                quantile_values = []
        # Parse data for overall
        else:
            quantile_values = data["overall"]["interval_real"]["q"]["value"]
        quantiles = dict(zip(data["overall"]["interval_real"]["q"]["q"], quantile_values))
        return quantiles

    def get_rc(self):
        return self.RC_TIME

    def explain(self):
        items = self.get_criterion_parameters()
        explanation = "Percentile %(percentile)s higher than %(limit)sms for %(seconds_count)ss, since %(since_time)s" \
            % items
        if self.tag:
            explanation = explanation + " for tag %(tag)s" % items
        return explanation

    def get_criterion_parameters(self):
        parameters = {
            'percentile': self.quantile,
            'limit': self.rt_limit,
            'seconds_count': self.seconds_count,
            'seconds_limit': self.seconds_limit,
            'since_time': self.cause_second[0].get("ts"),
            'tag': self.tag
        }
        return parameters

    def widget_explain(self):
        items = self.get_criterion_parameters()
        return "%(percentile)s%% >%(limit)sms for %(seconds_count)s/%(seconds_limit)ss" % items, \
            float(self.seconds_count) / self.seconds_limit


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
        items = self.get_criterion_parameters()
        return "Cumulative percentiles are steady for %ss, since %s" % items

    def get_criterion_parameters(self):
        parameters = (
            self.seconds_count, self.cause_second[0]["ts"])
        return parameters

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
        return "Test time elapsed. Limit: %(limit)ss, actual time: %(actual)ss" % self.get_criterion_parameters()

    def get_criterion_parameters(self):
        parameters = {
            'limit': self.time_limit,
            'actual': self.end_time - self.start_time
        }
        return parameters

    def widget_explain(self):
        return "Time limit: %(limit)ss, actual time: %(actual)ss" % self.get_criterion_parameters()
