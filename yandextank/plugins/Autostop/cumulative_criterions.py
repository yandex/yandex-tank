'''Cummulative Autostops'''

import logging
import math
import re
from collections import deque
from fractions import Fraction

import numpy as np
from ...common.util import expand_to_milliseconds, expand_to_seconds

from .criterions import AbstractCriterion

logger = logging.getLogger(__name__)


class WindowCounter(object):
    def __init__(self, window_size):
        self.window_size = window_size
        self.value = 0
        self.q = deque()

    def push(self, value):
        self.value += value
        self.q.append(value)
        if len(self.q) > self.window_size:
            self.value -= self.q.popleft()

    def __len__(self):
        return len(self.q)


def parse_codes_mask(mask_str):
    mask = mask_str.strip().lower()
    return mask, re.compile(mask.replace('x', '.'))


def parse_level(level_str):
    '''«10%» — доля от всех ответов окна, «10» — число ответов за окно'''
    level_str = level_str.strip()
    if level_str[-1:] == '%':
        # Fraction, а не float: точное попадание в порог не должно теряться на округлении.
        return Fraction(level_str[:-1]), True
    return int(level_str), False


def parse_window(window_str):
    window = expand_to_seconds(window_str)
    if window < 1:
        # Секундный разбор схлопывает '500ms' в ноль, а с пустым окном критерий молча не работает.
        raise ValueError("Autostop window must be at least 1s: %s" % window_str)
    return window


def select_tag(data, tag):
    '''Данные секунды по тегу критерия; None — в секунде нет ответов с этим тегом, она ничего не добавляет в окно'''
    if not tag:
        return data["overall"]
    return data["tagged"].get(tag) or None


def level_reached(counted, total, level, is_relative):
    if not is_relative:
        return counted >= level
    return total > 0 and counted * 100 >= level * total


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
        level, is_relative = parse_level(params[1])
        if not is_relative:
            raise ValueError("total_time ratio must be a percentage: %s" % params[1])
        self.fail_ratio_limit = level / 100
        self.window_size = parse_window(params[2])
        self.fail_counter = WindowCounter(self.window_size)
        self.total_counter = WindowCounter(self.window_size)
        self.total_fail_ratio = 0.0
        self.seconds = deque()
        self.tag = params[3].strip() if len(params) == 4 else None

    def __fail_count(self, part):
        hist = part["interval_real"]["hist"]
        # Бины агрегатора полуоткрытые [left, right): бин с правой границей на лимите целиком быстрее лимита.
        return int(np.sum(np.asarray(hist["data"])[np.asarray(hist["bins"]) > self.rt_limit]))

    def notify(self, data, stat):
        fail_count, total_responses = self.parse_data(data)
        self.seconds.append((data, stat))
        if len(self.seconds) > self.window_size:
            self.seconds.popleft()
        self.fail_counter.push(fail_count)
        self.total_counter.push(total_responses)
        total = self.total_counter.value
        self.total_fail_ratio = self.fail_counter.value / total if total else 0.0
        if len(self.fail_counter) >= self.window_size and level_reached(
            self.fail_counter.value, total, self.fail_ratio_limit * 100, True
        ):
            self.cause_second = self.seconds[0]
            logger.debug(self.explain())
            return True
        return False

    def parse_data(self, data):
        part = select_tag(data, self.tag)
        if part is None:
            return 0, 0
        return self.__fail_count(part), part["interval_real"]["len"]

    def get_rc(self):
        return self.RC_TOTAL_TIME

    def explain(self):
        items = self.get_criterion_parameters()
        explanation = "%(ratio).2f%% responses times higher than %(limit)sms for %(seconds_count)ss " % items
        if self.tag:
            explanation = explanation + " for tag %(tag)s" % items
        return explanation

    def get_criterion_parameters(self):
        parameters = {
            'ratio': self.total_fail_ratio * 100,
            'limit': self.rt_limit / 1000,
            'seconds_count': self.window_size,
            'tag': self.tag,
        }
        return parameters

    def widget_explain(self):
        items = self.get_criterion_parameters()
        return "%(ratio).2f%% times >%(limit)sms for %(seconds_count)ss" % items, self.total_fail_ratio


class AbstractCodesCriterion(AbstractCriterion):
    '''Общая часть total_http, total_net, negative_http и negative_net: сколько ответов накопилось за окно'''

    explain_template = ''
    widget_template = ''

    def __init__(self, autostop, param_str):
        AbstractCriterion.__init__(self)
        self.seconds_count = 0
        self.autostop = autostop
        params = param_str.split(',')
        self.codes_mask, self.codes_regex = parse_codes_mask(params[0])
        self.level, self.is_relative = parse_level(params[1])
        self.seconds_limit = parse_window(params[2])
        self.tag = params[3].strip() if len(params) == 4 else None
        self.counted = WindowCounter(self.seconds_limit)
        self.total = WindowCounter(self.seconds_limit)
        self.second_window = deque()

    def count(self, part):
        '''Сколько ответов секунды копит критерий'''
        raise NotImplementedError("Abstract methods requires overriding")

    def notify(self, data, stat):
        part = select_tag(data, self.tag)
        if part is None:
            counted, total = 0, 0
        else:
            counted, total = self.count(part), part["interval_real"]["len"]
        self.counted.push(counted)
        self.total.push(total)
        self.second_window.append((data, stat))
        if len(self.second_window) > self.seconds_limit:
            self.second_window.popleft()
        logger.debug(
            "%s %s: %s of %s responses, level %s",
            self.get_type_string(),
            self.codes_mask,
            self.counted.value,
            self.total.value,
            self.get_level_str(),
        )
        if len(self.second_window) >= self.seconds_limit and level_reached(
            self.counted.value, self.total.value, self.level, self.is_relative
        ):
            self.cause_second = self.second_window[0]
            logger.debug(self.explain())
            return True
        return False

    def get_level_str(self):
        '''format level str'''
        if self.is_relative:
            return '%g%%' % self.level
        return self.level

    def explain(self):
        items = self.get_criterion_parameters()
        explanation = self.explain_template % items
        if self.tag:
            explanation = explanation + " for tag %(tag)s" % items
        return explanation

    def get_criterion_parameters(self):
        parameters = {
            'code': self.codes_mask,
            'level': self.get_level_str(),
            'seconds_limit': self.seconds_limit,
            'tag': self.tag,
        }
        return parameters

    def widget_explain(self):
        explanation = self.widget_template % self.get_criterion_parameters()
        if self.is_relative:
            return explanation, (self.counted.value / self.total.value if self.total.value else 0.0)
        return explanation, 1.0


class TotalHTTPCodesCriterion(AbstractCodesCriterion):
    '''Cummulative HTTP Criterion'''

    explain_template = "%(code)s codes count higher than %(level)s for %(seconds_limit)ss"
    widget_template = "HTTP %(code)s>%(level)s for %(seconds_limit)ss"

    @staticmethod
    def get_type_string():
        return 'total_http'

    def count(self, part):
        return self.count_matched_codes(self.codes_regex, part["proto_code"]["count"])

    def get_rc(self):
        return self.RC_TOTAL_HTTP


class TotalNetCodesCriterion(AbstractCodesCriterion):
    '''Cummulative Net Criterion'''

    explain_template = "%(code)s net codes count higher than %(level)s for %(seconds_limit)ss"
    widget_template = "Net %(code)s>%(level)s for %(seconds_limit)ss"

    @staticmethod
    def get_type_string():
        return 'total_net'

    def count(self, part):
        codes = part["net_code"]["count"].copy()
        codes.pop('0', None)
        return self.count_matched_codes(self.codes_regex, codes)

    def get_rc(self):
        return self.RC_TOTAL_NET


class TotalNegativeHTTPCodesCriterion(AbstractCodesCriterion):
    '''Reversed HTTP Criterion'''

    explain_template = "Not %(code)s codes count higher than %(level)s for %(seconds_limit)ss"
    widget_template = "HTTP not %(code)s>%(level)s for %(seconds_limit)ss"

    @staticmethod
    def get_type_string():
        return 'negative_http'

    def count(self, part):
        return part["interval_real"]["len"] - self.count_matched_codes(self.codes_regex, part["proto_code"]["count"])

    def get_rc(self):
        return self.RC_TOTAL_NEGATIVE_HTTP


class TotalNegativeNetCodesCriterion(AbstractCodesCriterion):
    '''Reversed NET Criterion'''

    explain_template = "Not %(code)s codes count higher than %(level)s for %(seconds_limit)ss"
    widget_template = "Net not %(code)s>%(level)s for %(seconds_limit)ss"

    @staticmethod
    def get_type_string():
        return 'negative_net'

    def count(self, part):
        return part["interval_real"]["len"] - self.count_matched_codes(self.codes_regex, part["net_code"]["count"])

    def get_rc(self):
        return self.RC_TOTAL_NEGATIVE_NET


class TotalHTTPTrendCriterion(AbstractCriterion):
    '''HTTP Trend Criterion'''

    @staticmethod
    def get_type_string():
        return 'http_trend'

    def __init__(self, autostop, param_str):
        AbstractCriterion.__init__(self)
        self.seconds_count = 0
        params = param_str.split(',')
        self.codes_mask, self.codes_regex = parse_codes_mask(params[0])
        self.autostop = autostop
        self.tangents = deque()
        self.second_window = deque()
        self.total_tan = float()

        self.tangents.append(0)
        self.last = 0
        self.seconds_limit = parse_window(params[1])
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
            "Last trend for http codes %s: %.2f +/- %.2f", self.codes_mask, self.total_tan, self.measurement_error
        )

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
                    self.codes_regex, data["tagged"][self.tag]["proto_code"]["count"]
                )
            # matched_responses=0 if current tag differs from selected one
            else:
                matched_responses = 0
        # Count data for overall if it's present
        else:
            matched_responses = self.count_matched_codes(self.codes_regex, data["overall"]["proto_code"]["count"])
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
        return self.RC_TOTAL_HTTP_TREND

    def explain(self):
        items = self.get_criterion_parameters()
        return (
            "Last trend for %(code)s http codes "
            "is %(total_tan).2f +/- %(measurement_err).2f for %(seconds_limit)ss" % items
        )

    def get_criterion_parameters(self):
        parameters = {
            'code': self.codes_mask,
            'total_tan': self.total_tan,
            'measurement_err': self.measurement_error,
            'seconds_limit': self.seconds_limit,
            'tag': self.tag,
        }
        return parameters

    def widget_explain(self):
        items = self.get_criterion_parameters()
        return (
            "HTTP(%(code)s) trend is %(total_tan).2f +/- %(measurement_err).2f < 0 for %(seconds_limit)ss" % items,
            1.0,
        )
