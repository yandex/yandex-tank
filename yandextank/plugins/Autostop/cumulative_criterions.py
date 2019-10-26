''' Cummulative Autostops '''
import logging
import math
import re
from collections import deque

import numpy as np
from ...common.util import expand_to_milliseconds, expand_to_seconds

from .criterions import AbstractCriterion

logger = logging.getLogger(__name__)


class WindowCounter(object):
    def __init__(self, window_size):
        self.window_size = window_size
        self.value = 0.0
        self.q = deque()

    def push(self, value):
        self.value += value
        self.q.append(value)
        if len(self.q) > self.window_size:
            self.value -= self.q.popleft()

    def __len__(self):
        return len(self.q)


class TotalFracTimeCriterion(AbstractCriterion):
    '''
    Windowed time criterion

    syntax: total_time(300ms, 70%, 3s)

    Stop test if 70 percent of response times are greater then 300ms in
    a sliding window of 3 seconds.

    Warning: this criterion uses histogram to make its decision, so the
    time boundary is rounded to aggregator bin edge.
    '''

    @staticmethod
    def get_type_string():
        return 'total_time'

    def __init__(self, autostop, param_str):
        AbstractCriterion.__init__(self)
        self.autostop = autostop
        params = param_str.split(',')
        self.rt_limit = expand_to_milliseconds(params[0]) * 1000
        self.fail_ratio_limit = float(params[1][:-1]) / 100.0
        self.window_size = expand_to_seconds(params[2])
        self.fail_counter = WindowCounter(self.window_size)
        self.total_counter = WindowCounter(self.window_size)
        self.total_fail_ratio = 0.0
        self.seconds = deque()
        self.tag = params[3].strip() if len(params) == 4 else None

    def __fail_count(self, data):
        ecdf = np.cumsum(data["overall"]["interval_real"]["hist"]["data"])
        idx = np.searchsorted(data["overall"]["interval_real"]["hist"]["bins"], self.rt_limit)
        if self.tag:
            if data["tagged"].get(self.tag):
                ecdf = np.cumsum(data["tagged"][self.tag]["interval_real"]["hist"]["data"])
                idx = np.searchsorted(data["tagged"][self.tag]["interval_real"]["hist"]["bins"], self.rt_limit)
            else:
                idx = 0

        if idx == 0:
            return ecdf[-1]
        elif idx == len(ecdf):
            return 0
        else:
            return ecdf[-1] - ecdf[idx]

    def notify(self, data, stat):
        total_responses = self.parse_data(data)
        self.seconds.append((data, stat))
        self.fail_counter.push(self.__fail_count(data))
        self.total_counter.push(total_responses)
        self.total_fail_ratio = (
            self.fail_counter.value / self.total_counter.value)
        if self.total_fail_ratio >= self.fail_ratio_limit and len(
                self.fail_counter) >= self.window_size:
            self.cause_second = self.seconds[0]
            logger.debug(self.explain())
            return True
        if len(self.seconds) > self.window_size:
            self.seconds.popleft()
        return False

    def parse_data(self, data):
        # Parse data for specific tag if it's present
        if self.tag:
            if data["tagged"].get(self.tag):
                total_responses = data["tagged"][self.tag]["interval_real"]["len"]
            else:
                total_responses = data["overall"]["interval_real"]["len"]
        # Parse data for overall
        else:
            total_responses = data["overall"]["interval_real"]["len"]
        return total_responses

    def get_rc(self):
        return 25

    def explain(self):
        items = self.get_criterion_parameters()
        explanation = "%(ratio).2f%% responses times higher than %(limit)sms for %(seconds_count)ss " \
            "since: %(since_time)s" % items
        if self.tag:
            explanation = explanation + " for tag %(tag)s" % items
        return explanation

    def get_criterion_parameters(self):
        parameters = {
            'ratio': self.total_fail_ratio * 100,
            'limit': self.rt_limit / 1000,
            'seconds_count': self.window_size,
            'since_time': self.cause_second[0]["ts"],
            'tag': self.tag
        }
        return parameters

    def widget_explain(self):
        items = self.get_criterion_parameters()
        return "%(ratio).2f%% times >%(limit)sms for %(seconds_count)ss" % items, self.total_fail_ratio


class TotalHTTPCodesCriterion(AbstractCriterion):
    ''' Cummulative HTTP Criterion '''

    @staticmethod
    def get_type_string():
        return 'total_http'

    def __init__(self, autostop, param_str):
        AbstractCriterion.__init__(self)
        self.seconds_count = 0
        params = param_str.split(',')
        self.codes_mask = params[0].lower()
        self.codes_regex = re.compile(self.codes_mask.replace("x", '.'))
        self.autostop = autostop
        self.data = deque()
        self.second_window = deque()

        level_str = params[1].strip()
        if level_str[-1:] == '%':
            self.level = float(level_str[:-1])
            self.is_relative = True
        else:
            self.level = int(level_str)
            self.is_relative = False
        self.seconds_limit = expand_to_seconds(params[2])
        self.tag = params[3].strip() if len(params) == 4 else None

    def notify(self, data, stat):
        matched_responses, total_responses = self.parse_data(data)
        if self.is_relative:
            if total_responses > 0:
                matched_responses = float(matched_responses) / total_responses * 100
            else:
                matched_responses = 1
        logger.debug(
            "HTTP codes matching mask %s: %s/%s", self.codes_mask,
            matched_responses, self.level)
        self.data.append(matched_responses)
        self.second_window.append((data, stat))
        if len(self.data) > self.seconds_limit:
            self.data.popleft()
            self.second_window.popleft()
        queue_len = 1
        if self.is_relative:
            queue_len = len(self.data)
        if (sum(self.data) / queue_len) >= self.level\
                and len(self.data) >= self.seconds_limit:  # yapf:disable
            self.cause_second = self.second_window[0]
            logger.debug(self.explain())
            return True
        return False

    def parse_data(self, data):
        # Parse data for specific tag if it is present
        if self.tag:
            if data["tagged"].get(self.tag):
                matched_responses = self.count_matched_codes(
                    self.codes_regex, data["tagged"][self.tag]["proto_code"]["count"])
                total_responses = data["tagged"][self.tag]["interval_real"]["len"]
            # matched_responses=0 if current tag differs from selected one
            else:
                matched_responses = 0
                total_responses = data["overall"]["interval_real"]["len"]
        # Parse data for overall
        else:
            matched_responses = self.count_matched_codes(
                self.codes_regex, data["overall"]["proto_code"]["count"])
            total_responses = data["overall"]["interval_real"]["len"]
        return matched_responses, total_responses

    def get_rc(self):
        return 26

    def get_level_str(self):
        ''' format level str '''
        if self.is_relative:
            level_str = str(self.level) + "%"
        else:
            level_str = self.level
        return level_str

    def explain(self):
        items = self.get_criterion_parameters()
        explanation = "%(code)s codes count higher than %(level)s for %(seconds_limit)ss, since %(since_time)s" % items
        if self.tag:
            explanation = explanation + " for tag %(tag)s" % items
        return explanation

    def get_criterion_parameters(self):
        parameters = {
            'code': self.codes_mask,
            'level': self.get_level_str(),
            'seconds_limit': self.seconds_limit,
            'since_time': self.cause_second[0]["ts"],
            'tag': self.tag
        }
        return parameters

    def widget_explain(self):
        items = self.get_criterion_parameters()
        explanation = "HTTP %(code)s>%(level)s for %(seconds_limit)ss" % items
        if self.is_relative:
            return explanation, sum(self.data)
        return explanation, 1.0


class TotalNetCodesCriterion(AbstractCriterion):
    ''' Cummulative Net Criterion '''

    @staticmethod
    def get_type_string():
        return 'total_net'

    def __init__(self, autostop, param_str):
        AbstractCriterion.__init__(self)
        self.seconds_count = 0
        params = param_str.split(',')
        self.codes_mask = params[0].lower()
        self.codes_regex = re.compile(self.codes_mask.replace("x", '.'))
        self.autostop = autostop
        self.data = deque()
        self.second_window = deque()

        level_str = params[1].strip()
        if level_str[-1:] == '%':
            self.level = float(level_str[:-1])
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
                matched_responses = float(matched_responses) / total_responses * 100
                logger.debug(
                    "Net codes matching mask %s: %s%%/%s", self.codes_mask,
                    round(matched_responses, 2), self.get_level_str())
            else:
                matched_responses = 1
        else:
            logger.debug(
                "Net codes matching mask %s: %s/%s", self.codes_mask,
                matched_responses, self.get_level_str())

        self.data.append(matched_responses)
        self.second_window.append((data, stat))
        if len(self.data) > self.seconds_limit:
            self.data.popleft()
            self.second_window.popleft()

        queue_len = 1
        if self.is_relative:
            queue_len = len(self.data)
        if (sum(self.data) / queue_len) >= self.level\
                and len(self.data) >= self.seconds_limit:  # yapf:disable
            self.cause_second = self.second_window[0]
            logger.debug(self.explain())
            return True
        return False

    def parse_data(self, data):
        # Count data for specific tag if it's present
        if self.tag:
            if data["tagged"].get(self.tag):
                codes = data["tagged"][self.tag]["net_code"]["count"].copy()
                if '0' in codes:
                    codes.pop('0')
                matched_responses = self.count_matched_codes(self.codes_regex, codes)
                total_responses = data["tagged"][self.tag]["interval_real"]["len"]
            # matched_responses=0 if current tag differs from selected one
            else:
                matched_responses = 0
                total_responses = data["overall"]["interval_real"]["len"]
        # Count data for overall
        else:
            codes = data["overall"]["net_code"]["count"].copy()
            if '0' in codes:
                codes.pop('0')
            matched_responses = self.count_matched_codes(self.codes_regex, codes)
            total_responses = data["overall"]["interval_real"]["len"]
        return matched_responses, total_responses

    def get_rc(self):
        return 27

    def get_level_str(self):
        ''' format level str '''
        if self.is_relative:
            level_str = str(self.level) + "%"
        else:
            level_str = str(self.level)
        return level_str

    def explain(self):
        items = self.get_criterion_parameters()
        explanation = "%(code)s net codes count higher than %(level)s for %(seconds_limit)ss, since %(since_time)s" \
            % items
        if self.tag:
            explanation = explanation + " for tag %(tag)s" % items
        return explanation

    def get_criterion_parameters(self):
        parameters = {
            'code': self.codes_mask,
            'level': self.get_level_str(),
            'seconds_limit': self.seconds_limit,
            'since_time': self.cause_second[0]["ts"],
            'tag': self.tag
        }
        return parameters

    def widget_explain(self):
        items = self.get_criterion_parameters()
        explanation = "Net %(code)s>%(level)s for %(seconds_limit)ss" % items
        if self.is_relative:
            return explanation, sum(self.data)
        return explanation, 1.0


class TotalNegativeHTTPCodesCriterion(AbstractCriterion):
    ''' Reversed HTTP Criterion '''

    @staticmethod
    def get_type_string():
        return 'negative_http'

    def __init__(self, autostop, param_str):
        AbstractCriterion.__init__(self)
        self.seconds_count = 0
        params = param_str.split(',')
        self.codes_mask = params[0].lower()
        self.codes_regex = re.compile(self.codes_mask.replace("x", '.'))
        self.autostop = autostop
        self.data = deque()
        self.second_window = deque()

        level_str = params[1].strip()
        if level_str[-1:] == '%':
            self.level = float(level_str[:-1])
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
                matched_responses = float(matched_responses) / total_responses * 100
                matched_responses = 100 - matched_responses
            else:
                matched_responses = 1
            logger.debug(
                "HTTP codes matching mask not %s: %s/%s", self.codes_mask,
                round(matched_responses, 1), self.level)
        else:
            matched_responses = (
                total_responses - matched_responses)
            logger.debug(
                "HTTP codes matching mask not %s: %s/%s", self.codes_mask,
                matched_responses, self.level)
        self.data.append(matched_responses)
        self.second_window.append((data, stat))
        if len(self.data) > self.seconds_limit:
            self.data.popleft()
            self.second_window.popleft()

        queue_len = 1
        if self.is_relative:
            queue_len = len(self.data)
        if (sum(self.data) / queue_len) >= self.level\
                and len(self.data) >= self.seconds_limit:  # yapf:disable
            self.cause_second = self.second_window[0]
            logger.debug(self.explain())
            return True
        return False

    def parse_data(self, data):
        # Parse data for specific tag if it is present
        if self.tag:
            if data["tagged"].get(self.tag):
                matched_responses = self.count_matched_codes(
                    self.codes_regex, data["tagged"][self.tag]["proto_code"]["count"])
                total_responses = data["tagged"][self.tag]["interval_real"]["len"]
            # matched_responses=0 if current tag differs from selected one
            else:
                matched_responses = 0
                total_responses = data["overall"]["interval_real"]["len"]
        # Parse data for overall
        else:
            matched_responses = self.count_matched_codes(
                self.codes_regex, data["overall"]["proto_code"]["count"])
            total_responses = data["overall"]["interval_real"]["len"]
        return matched_responses, total_responses

    def get_rc(self):
        return 28

    def get_level_str(self):
        ''' format level str'''
        if self.is_relative:
            level_str = str(self.level) + "%"
        else:
            level_str = self.level
        return level_str

    def explain(self):
        items = self.get_criterion_parameters()
        explanation = "Not %(code)s codes count higher than %(level)s for %(seconds_limit)ss, since %(since_time)s" % items
        if self.tag:
            explanation = explanation + " for tag %(tag)s" % items
        return explanation

    def get_criterion_parameters(self):
        parameters = {
            'code': self.codes_mask,
            'level': self.get_level_str(),
            'seconds_limit': self.seconds_limit,
            'since_time': self.cause_second[0]["ts"],
            'tag': self.tag
        }
        return parameters

    def widget_explain(self):
        items = self.get_criterion_parameters()
        explanation = "HTTP not %(code)s>%(level)s for %(seconds_limit)ss" % items
        if self.is_relative:
            return explanation, sum(self.data)
        return explanation, 1.0


class TotalNegativeNetCodesCriterion(AbstractCriterion):
    ''' Reversed NET Criterion '''

    @staticmethod
    def get_type_string():
        return 'negative_net'

    def __init__(self, autostop, param_str):
        AbstractCriterion.__init__(self)
        self.seconds_count = 0
        params = param_str.split(',')
        self.codes_mask = params[0].lower()
        self.codes_regex = re.compile(self.codes_mask.replace("x", '.'))
        self.autostop = autostop
        self.data = deque()
        self.second_window = deque()

        level_str = params[1].strip()
        if level_str[-1:] == '%':
            self.level = float(level_str[:-1])
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
                matched_responses = float(matched_responses) / total_responses * 100
                matched_responses = 100 - matched_responses
            else:
                matched_responses = 1
            logger.debug(
                "Net codes matching mask not %s: %s/%s", self.codes_mask,
                round(matched_responses, 1), self.level)
        else:
            matched_responses = (
                total_responses - matched_responses)
            logger.debug(
                "Net codes matching mask not %s: %s/%s", self.codes_mask,
                matched_responses, self.level)
        self.data.append(matched_responses)
        self.second_window.append((data, stat))
        if len(self.data) > self.seconds_limit:
            self.data.popleft()
            self.second_window.popleft()

        queue_len = 1
        if self.is_relative:
            queue_len = len(self.data)
        if (sum(self.data) / queue_len) >= self.level \
                and len(self.data) >= self.seconds_limit:  # yapf:disable
            self.cause_second = self.second_window[0]
            logger.debug(self.explain())
            return True
        return False

    def parse_data(self, data):
        # Count data for specific tag if it's present
        if self.tag:
            if data["tagged"].get(self.tag):
                codes = data["tagged"][self.tag]["net_code"]["count"].copy()
                if '0' in codes:
                    codes.pop('0')
                matched_responses = self.count_matched_codes(self.codes_regex, codes)
                total_responses = data["tagged"][self.tag]["interval_real"]["len"]
            # matched_responses=0 if current tag differs from selected one
            else:
                matched_responses = 0
                total_responses = data["overall"]["interval_real"]["len"]
        # Count data for overall
        else:
            codes = data["overall"]["net_code"]["count"].copy()
            if '0' in codes:
                codes.pop('0')
            matched_responses = self.count_matched_codes(self.codes_regex, codes)
            total_responses = data["overall"]["interval_real"]["len"]
        return matched_responses, total_responses

    def get_rc(self):
        return 29

    def get_level_str(self):
        ''' format level str'''
        if self.is_relative:
            level_str = str(self.level) + "%"
        else:
            level_str = self.level
        return level_str

    def explain(self):
        items = self.get_criterion_parameters()
        explanation = "Not %(code)s codes count higher than %(level)s for %(seconds_limit)ss, since %(since_time)s"\
            % items
        if self.tag:
            explanation = explanation + " for tag %(tag)s" % items
        return explanation

    def get_criterion_parameters(self):
        parameters = {
            'code': self.codes_mask,
            'level': self.get_level_str(),
            'seconds_limit': self.seconds_limit,
            'since_time': self.cause_second[0]["ts"],
            'tag': self.tag
        }
        return parameters

    def widget_explain(self):
        items = self.get_criterion_parameters()
        explanation = "Net not %(code)s>%(level)s for %(seconds_limit)ss" % items
        if self.is_relative:
            return explanation, sum(self.data)
        return explanation, 1.0


class TotalHTTPTrendCriterion(AbstractCriterion):
    ''' HTTP Trend Criterion '''

    @staticmethod
    def get_type_string():
        return 'http_trend'

    def __init__(self, autostop, param_str):
        AbstractCriterion.__init__(self)
        self.seconds_count = 0
        params = param_str.split(',')
        self.codes_mask = params[0].lower()
        self.codes_regex = re.compile(self.codes_mask.replace("x", '.'))
        self.autostop = autostop
        self.tangents = deque()
        self.second_window = deque()
        self.total_tan = float()

        self.tangents.append(0)
        self.last = 0
        self.seconds_limit = expand_to_seconds(params[1])
        self.measurement_error = float()
        self.tag = params[2].strip() if len(params) == 3 else None

    def notify(self, data, stat):
        matched_responses = self.parse_data(data)
        self.tangents.append(matched_responses - self.last)
        self.second_window.append((data, stat))

        self.last = matched_responses

        if len(self.tangents) > self.seconds_limit:
            self.tangents.popleft()
            self.second_window.popleft()

        self.measurement_error = self.calc_measurement_error(self.tangents)

        self.total_tan = float(sum(self.tangents) / len(self.tangents))
        logger.debug(
            "Last trend for http codes %s: %.2f +/- %.2f", self.codes_mask,
            self.total_tan, self.measurement_error)

        if self.total_tan + self.measurement_error < 0:
            self.cause_second = self.second_window[0]
            logger.debug(self.explain())
            return True

        return False

    def parse_data(self, data):
        # Count data for specific tag if it's present
        if self.tag:
            if data["tagged"].get(self.tag):
                matched_responses = self.count_matched_codes(
                    self.codes_regex, data["tagged"][self.tag]["proto_code"]["count"])
            # matched_responses=0 if current tag differs from selected one
            else:
                matched_responses = 0
        # Count data for overall if it's present
        else:
            matched_responses = self.count_matched_codes(
                self.codes_regex, data["overall"]["proto_code"]["count"])
        return matched_responses

    def calc_measurement_error(self, tangents):
        '''
        formula for measurement error
        sqrt ( (sum(1, n, (k_i - <k>)**2) / (n*(n-1)))
        '''

        if len(tangents) < 2:
            return 0.0

        avg_tan = float(sum(tangents) / len(tangents))
        numerator = float()
        for i in tangents:
            numerator += (i - avg_tan) * (i - avg_tan)

        return math.sqrt(numerator / len(tangents) / (len(tangents) - 1))

    def get_rc(self):
        return 30

    def explain(self):
        items = self.get_criterion_parameters()
        return "Last trend for %(code)s http codes " \
            "is %(total_tan).2f +/- %(measurement_err).2f for %(seconds_limit)ss, since %(since_time)s" % items

    def get_criterion_parameters(self):
        parameters = {
            'code': self.codes_mask,
            'total_tan': self.total_tan,
            'measurement_err': self.measurement_error,
            'seconds_limit': self.seconds_limit,
            'since_time': self.cause_second[0]["ts"],
            'tag': self.tag
        }
        return parameters

    def widget_explain(self):
        items = self.get_criterion_parameters()
        return "HTTP(%(code)s) trend is %(total_tan).2f +/- %(measurement_err).2f < 0 for %(seconds_limit)ss" % items, 1.0


class QuantileOfSaturationCriterion(AbstractCriterion):
    ''' Quantile of Saturation Criterion
        example: qsat(50ms, 3m, 10%) '''

    @staticmethod
    def get_type_string():
        return 'qsat'

    def __init__(self, autostop, param_str):
        AbstractCriterion.__init__(self)
        raise NotImplementedError

    #     self.autostop = autostop
    #     self.data = deque()
    #     self.second_window = deque()

    #     params = param_str.split(',')
    #     # qunatile in ms
    #     self.timing = expand_to_milliseconds(params[0])
    #     # width of time in seconds
    #     self.width = expand_to_seconds(params[1])
    #     # max height of deviations in percents
    #     self.height = float(params[2].split('%')[0])
    #     # last deviation in percents
    #     self.deviation = float()

    # def __get_timing_quantile(self, data):
    #     ''' get quantile level for criterion timing '''
    #     quan = 0.0
    #     for timing in sorted(aggr_data.cumulative.times_dist.keys()):
    #         timing_item = aggr_data.cumulative.times_dist[timing]
    #         quan += float(timing_item[
    #             'count']) / aggr_data.cumulative.total_count
    #         logger.debug("tt: %s %s", self.timing, timing_item['to'])
    #         if self.timing <= timing_item['to']:
    #             return quan
    #     return quan

    # def notify(self, data, stat):
    #     quan = 100 * self.__get_timing_quantile(data)
    #     logger.debug("Quantile for %s: %s", self.timing, quan)

    #     self.data.append(quan)
    #     self.second_window.append((data, stat))

    #     if len(self.data) > self.width:
    #         self.autostop.add_counting(self)
    #         self.data.popleft()
    #         self.second_window.popleft()

    #         self.deviation = max(self.data) - min(self.data)
    #         logger.debug(self.explain())

    #         if self.deviation < self.height:
    #             return True
    #     return False

    # def get_rc(self):
    #     return 33

    # def explain(self):
    #     items = (self.timing, self.width, self.deviation, self.height)
    #     return "%sms variance for %ss: %.3f%% (<%s%%)" % items

    # def widget_explain(self):
    #     level = self.height / self.deviation
    #     items = (self.timing, self.width, self.deviation, self.height)
    #     return ("%sms variance for %ss: %.3f%% (<%s%%)" % items, level)
