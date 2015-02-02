''' Cummulative Autostops '''
from Aggregator import AggregateResultListener
from Autostop import AbstractCriteria, AutostopPlugin

from yandextank.core import AbstractPlugin
import yandextank.core as tankcore

from collections import deque
import re
import math

class TotalAutostopPlugin(AbstractPlugin, AggregateResultListener):
    ''' Cummulative Criterias Plugin '''
    SECTION = 'autostop'
    @staticmethod
    def get_key():
        return __file__

    def configure(self):
        autostop = self.core.get_plugin_of_type(AutostopPlugin)
        autostop.add_criteria_class(TotalFracTimeCriteria)
        autostop.add_criteria_class(TotalHTTPCodesCriteria)
        autostop.add_criteria_class(TotalNetCodesCriteria)
        autostop.add_criteria_class(TotalNegativeHTTPCodesCriteria)
        autostop.add_criteria_class(TotalNegativeNetCodesCriteria)
        autostop.add_criteria_class(TotalHTTPTrendCriteria)
        autostop.add_criteria_class(QuantileOfSaturationCriteria)

    def prepare_test(self):
        pass

    def start_test(self):
        pass

    def end_test(self, retcode):
        pass

    def aggregate_second(self, second_aggregate_data):
        pass

class TotalFracTimeCriteria(AbstractCriteria):
    ''' Cummulative Time Criteria '''
    @staticmethod
    def get_type_string():
        return 'total_time'

    def __init__(self, autostop, param_str):
        AbstractCriteria.__init__(self)
        param = param_str.split(',')
        self.seconds_count = 0
        self.rt_limit = tankcore.expand_to_milliseconds(param[0])
        self.frac = param[1][:-1]
        self.seconds_limit = tankcore.expand_to_seconds(param[2])
        self.autostop = autostop
        self.data = deque()
        self.second_window = deque()
        self.real_frac = float()

    def notify(self, aggregate_second):
        failcnt = 0
        cnt = 0
        for i in reversed(aggregate_second.overall.times_dist):
            if i['from'] >= self.rt_limit :
                failcnt += i['count']
            cnt += i['count']
        if cnt != 0 :
            value = float(failcnt) / cnt
        else :
            value = 0
        self.data.append(value)
        self.second_window.append(aggregate_second)
        if len(self.data) > self.seconds_limit:
            self.data.popleft()
            self.second_window.popleft()

        self.real_frac = float(sum(self.data)) / len(self.data) * 100
        if self.real_frac >= float(self.frac) and len(self.data) >= self.seconds_limit:
            self.cause_second = self.second_window[0]
            self.log.debug(self.explain())
#            self.autostop.add_counting(self)
            return True
        return False

    def get_rc(self):
        return 25

    def explain(self):
        items = (round(self.real_frac, 2), self.rt_limit, self.seconds_limit, self.cause_second.time)
        return "%s%% responses times higher than %sms for %ss since: %s" % items

    def widget_explain(self):
        items = (round(self.real_frac, 2), self.rt_limit, self.seconds_limit)
        return ("%s%% Times >%sms for %ss" % items, self.real_frac)

class TotalHTTPCodesCriteria(AbstractCriteria):
    ''' Cummulative HTTP Criteria '''
    @staticmethod
    def get_type_string():
        return 'total_http'

    def __init__(self, autostop, param_str):
        AbstractCriteria.__init__(self)
        self.seconds_count = 0
        self.codes_mask = param_str.split(',')[0].lower()
        self.codes_regex = re.compile(self.codes_mask.replace("x", '.'))
        self.autostop = autostop
        self.data = deque()
        self.second_window = deque()

        level_str = param_str.split(',')[1].strip()
        if level_str[-1:] == '%':
            self.level = float(level_str[:-1])
            self.is_relative = True
        else:
            self.level = int(level_str)
            self.is_relative = False
        self.seconds_limit = tankcore.expand_to_seconds(param_str.split(',')[2])

    def notify(self, aggregate_second):
        matched_responses = self.count_matched_codes(self.codes_regex, aggregate_second.overall.http_codes)
        if self.is_relative:
            if aggregate_second.overall.RPS:
                matched_responses = float(matched_responses) / aggregate_second.overall.RPS * 100
            else:
                matched_responses = 1
        self.log.debug("HTTP codes matching mask %s: %s/%s", self.codes_mask, matched_responses, self.level)
        self.data.append(matched_responses)
        self.second_window.append(aggregate_second)
        if len(self.data) > self.seconds_limit :
            self.data.popleft()
            self.second_window.popleft()
        queue_len = 1
        if self.is_relative :
            queue_len = len(self.data)
        if (sum(self.data) / queue_len) >= self.level and len(self.data) >= self.seconds_limit:
            self.cause_second = self.second_window[0]
            self.log.debug(self.explain())
#            self.autostop.add_counting(self)
            return True
        return False

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
        if self.is_relative:
            items = (self.codes_mask, self.get_level_str(), self.seconds_limit, self.cause_second.time)
            return "%s codes count higher than %s for %ss, ended at: %s" % items
        items = (self.codes_mask, self.get_level_str(), self.seconds_limit, self.cause_second.time)
        return "%s codes count higher than %s for %ss, since %s" % items

    def widget_explain(self):
        if self.is_relative:
            items = (self.codes_mask, self.get_level_str(), self.seconds_limit)
            return ("HTTP %s>%s for %ss" % items, sum(self.data))
        items = (self.codes_mask, self.get_level_str(), self.seconds_limit)
        return ("HTTP %s>%s for %ss" % items, 1.0)

class TotalNetCodesCriteria(AbstractCriteria):
    ''' Cummulative Net Criteria '''
    @staticmethod
    def get_type_string():
        return 'total_net'

    def __init__(self, autostop, param_str):
        AbstractCriteria.__init__(self)
        self.seconds_count = 0
        self.codes_mask = param_str.split(',')[0].lower()
        self.codes_regex = re.compile(self.codes_mask.replace("x", '.'))
        self.autostop = autostop
        self.data = deque()
        self.second_window = deque()

        level_str = param_str.split(',')[1].strip()
        if level_str[-1:] == '%':
            self.level = float(level_str[:-1])
            self.is_relative = True
        else:
            self.level = int(level_str)
            self.is_relative = False
        self.seconds_limit = tankcore.expand_to_seconds(param_str.split(',')[2])


    def notify(self, aggregate_second):
        codes = aggregate_second.overall.net_codes.copy()
        if '0' in codes.keys():
            codes.pop('0')
        matched_responses = self.count_matched_codes(self.codes_regex, codes)
        if self.is_relative:
            if aggregate_second.overall.RPS:
                matched_responses = float(matched_responses) / aggregate_second.overall.RPS * 100
                self.log.debug("Net codes matching mask %s: %s%%/%s", self.codes_mask, round(matched_responses, 2), self.get_level_str())
            else:
                matched_responses = 1
        else : self.log.debug("Net codes matching mask %s: %s/%s", self.codes_mask, matched_responses, self.get_level_str())

        self.data.append(matched_responses)
        self.second_window.append(aggregate_second)
        if len(self.data) > self.seconds_limit :
            self.data.popleft()
            self.second_window.popleft()

        queue_len = 1
        if self.is_relative :
            queue_len = len(self.data)
        if (sum(self.data) / queue_len) >= self.level and len(self.data) >= self.seconds_limit:
            self.cause_second = self.second_window[0]
            self.log.debug(self.explain())
#            self.autostop.add_counting(self)
            return True
        return False

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
        if self.is_relative:
            items = (self.codes_mask, self.get_level_str(), self.seconds_limit, self.cause_second.time)
            return "%s net codes count higher than %s for %ss, since %s" % items
        items = (self.codes_mask, self.get_level_str(), self.seconds_limit, self.cause_second.time)
        return "%s net codes count higher than %s for %ss, since %s" % items

    def widget_explain(self):
        if self.is_relative:
            items = (self.codes_mask, self.get_level_str(), self.seconds_limit)
            return ("Net %s>%s for %ss" % items, self.level)
        items = (self.codes_mask, self.get_level_str(), self.seconds_limit)
        return ("Net %s>%s for %ss" % items, self.level)

class TotalNegativeHTTPCodesCriteria(AbstractCriteria):
    ''' Reversed HTTP Criteria '''
    @staticmethod
    def get_type_string():
        return 'negative_http'

    def __init__(self, autostop, param_str):
        AbstractCriteria.__init__(self)
        self.seconds_count = 0
        self.codes_mask = param_str.split(',')[0].lower()
        self.codes_regex = re.compile(self.codes_mask.replace("x", '.'))
        self.autostop = autostop
        self.data = deque()
        self.second_window = deque()

        level_str = param_str.split(',')[1].strip()
        if level_str[-1:] == '%':
            self.level = float(level_str[:-1])
            self.is_relative = True
        else:
            self.level = int(level_str)
            self.is_relative = False
        self.seconds_limit = tankcore.expand_to_seconds(param_str.split(',')[2])

    def notify(self, aggregate_second):
        matched_responses = self.count_matched_codes(self.codes_regex, aggregate_second.overall.http_codes)
        if self.is_relative:
            if aggregate_second.overall.RPS:
                matched_responses = float(matched_responses) / aggregate_second.overall.RPS * 100
                matched_responses = 100 - matched_responses
            else:
                matched_responses = 1
            self.log.debug("HTTP codes matching mask not %s: %s/%s", self.codes_mask, round(matched_responses, 1), self.level)
        else :
            matched_responses = aggregate_second.overall.RPS - matched_responses
            self.log.debug("HTTP codes matching mask not %s: %s/%s", self.codes_mask, matched_responses, self.level)
        self.data.append(matched_responses)
        self.second_window.append(aggregate_second)
        if len(self.data) > self.seconds_limit :
            self.data.popleft()
            self.second_window.popleft()

        queue_len = 1
        if self.is_relative :
            queue_len = len(self.data)
        if (sum(self.data) / queue_len) >= self.level and len(self.data) >= self.seconds_limit:
            self.cause_second = self.second_window[0]
            self.log.debug(self.explain())
#            self.autostop.add_counting(self)
            return True
        return False

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
        if self.is_relative:
            items = (self.codes_mask, self.get_level_str(), self.seconds_limit, self.cause_second.time)
            return "Not %s codes count higher than %s for %ss, since %s" % items
        items = (self.codes_mask, self.get_level_str(), self.seconds_limit, self.cause_second.time)
        return "Not %s codes count higher than %s for %ss, since %s" % items

    def widget_explain(self):
        if self.is_relative:
            items = (self.codes_mask, self.get_level_str(), self.seconds_limit)
            return ("HTTP not %s>%s for %ss" % items, sum(self.data))
        items = (self.codes_mask, self.get_level_str(), self.seconds_limit)
        return ("HTTP not %s>%s for %ss" % items, 1.0)

class TotalNegativeNetCodesCriteria(AbstractCriteria):
    ''' Reversed NET Criteria '''
    @staticmethod
    def get_type_string():
        return 'negative_net'

    def __init__(self, autostop, param_str):
        AbstractCriteria.__init__(self)
        self.seconds_count = 0
        self.codes_mask = param_str.split(',')[0].lower()
        self.codes_regex = re.compile(self.codes_mask.replace("x", '.'))
        self.autostop = autostop
        self.data = deque()
        self.second_window = deque()

        level_str = param_str.split(',')[1].strip()
        if level_str[-1:] == '%':
            self.level = float(level_str[:-1])
            self.is_relative = True
        else:
            self.level = int(level_str)
            self.is_relative = False
        self.seconds_limit = tankcore.expand_to_seconds(param_str.split(',')[2])

    def notify(self, aggregate_second):
        codes = aggregate_second.overall.net_codes.copy()
        # if '0' in codes.keys():
        #     codes.pop('0')
        matched_responses = self.count_matched_codes(self.codes_regex, codes)
        if self.is_relative:
            if aggregate_second.overall.RPS:
                matched_responses = float(matched_responses) / aggregate_second.overall.RPS * 100
                matched_responses = 100 - matched_responses
            else:
                matched_responses = 1
            self.log.debug("Net codes matching mask not %s: %s/%s", self.codes_mask, round(matched_responses, 1), self.level)
        else :
            matched_responses = aggregate_second.overall.RPS - matched_responses
            self.log.debug("Net codes matching mask not %s: %s/%s", self.codes_mask, matched_responses, self.level)
        self.data.append(matched_responses)
        self.second_window.append(aggregate_second)
        if len(self.data) > self.seconds_limit :
            self.data.popleft()
            self.second_window.popleft()

        queue_len = 1
        if self.is_relative :
            queue_len = len(self.data)
        if (sum(self.data) / queue_len) >= self.level and len(self.data) >= self.seconds_limit:
            self.cause_second = self.second_window[0]
            self.log.debug(self.explain())
            return True
        return False

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
        if self.is_relative:
            items = (self.codes_mask, self.get_level_str(), self.seconds_limit, self.cause_second.time)
            return "Not %s codes count higher than %s for %ss, since %s" % items
        items = (self.codes_mask, self.get_level_str(), self.seconds_limit, self.cause_second.time)
        return "Not %s codes count higher than %s for %ss, since %s" % items

    def widget_explain(self):
        if self.is_relative:
            items = (self.codes_mask, self.get_level_str(), self.seconds_limit)
            return ("Net not %s>%s for %ss" % items, sum(self.data))
        items = (self.codes_mask, self.get_level_str(), self.seconds_limit)
        return ("Net not %s>%s for %ss" % items, 1.0)

class TotalHTTPTrendCriteria(AbstractCriteria):
    ''' HTTP Trend Criteria '''

    @staticmethod
    def get_type_string():
        return 'http_trend'

    def __init__(self, autostop, param_str):
        AbstractCriteria.__init__(self)
        self.seconds_count = 0
        self.codes_mask = param_str.split(',')[0].lower()
        self.codes_regex = re.compile(self.codes_mask.replace("x", '.'))
        self.autostop = autostop
        self.tangents = deque()
        self.second_window = deque()
        self.total_tan = float()

        self.tangents.append(0)
        self.last = 0
        self.seconds_limit = tankcore.expand_to_seconds(param_str.split(',')[1])
        self.measurement_error = float()

    def notify(self, aggregate_second):
        matched_responses = self.count_matched_codes(self.codes_regex, aggregate_second.overall.http_codes)

        self.tangents.append(matched_responses - self.last)
        self.second_window.append(aggregate_second)

        self.last = matched_responses

        if len(self.tangents) > self.seconds_limit :
            self.tangents.popleft()
            self.second_window.popleft()

        self.measurement_error = self.calc_measurement_error(self.tangents)

        self.total_tan = float(sum(self.tangents) / len (self.tangents))
        self.log.debug("Last trend for http codes %s: %.2f +/- %.2f", self.codes_mask, self.total_tan, self.measurement_error)

        if self.total_tan + self.measurement_error < 0 :
            self.cause_second = self.second_window[0]
            self.log.debug(self.explain())
            return True

        return False

    def calc_measurement_error(self, tangents):
        ''' formula for measurement error sqrt ( (sum(1, n, (k_i - <k>)**2) / (n*(n-1))) '''

        if len(tangents) < 2 :
            return 0.0

        avg_tan = float(sum(tangents) / len(tangents))
        numerator = float()
        for i in tangents:
            numerator += (i - avg_tan) * (i - avg_tan)

        return math.sqrt (numerator / len(tangents) / (len(tangents) - 1))

    def get_rc(self):
        return 30

    def explain(self):
        items = (self.codes_mask, self.total_tan, self.measurement_error, self.seconds_limit, self.cause_second.time)
        return "Last trend for %s http codes is %.2f +/- %.2f for %ss, since %s" % items

    def widget_explain(self):
        items = (self.codes_mask, self.total_tan, self.measurement_error, self.seconds_limit)
        return ("HTTP(%s) trend is %.2f +/- %.2f < 0 for %ss" % items, 1.0)



class QuantileOfSaturationCriteria(AbstractCriteria):
    ''' Quantile of Saturation Criteria
        example: qsat(50ms, 3m, 10%) '''

    @staticmethod
    def get_type_string():
        return 'qsat'

    def __init__(self, autostop, param_str):
        AbstractCriteria.__init__(self)
        self.autostop = autostop
        self.data = deque()
        self.second_window = deque()

        params = param_str.split(',')
        # qunatile in ms
        self.timing = tankcore.expand_to_milliseconds(params[0])
        # width of time in seconds
        self.width = tankcore.expand_to_seconds(params[1])
        # max height of deviations in percents
        self.height = float(params[2].split('%')[0])
        # last deviation in percents
        self.deviation = float()


    def __get_timing_quantile(self, aggr_data):
        ''' get quantile level for criteria timing '''
        quan = 0.0
        for timing in sorted(aggr_data.cumulative.times_dist.keys()):
            timing_item = aggr_data.cumulative.times_dist[timing]
            quan += float(timing_item['count']) / aggr_data.cumulative.total_count
            self.log.debug("tt: %s %s", self.timing, timing_item['to'])
            if self.timing <= timing_item['to']:
                return quan
        return quan


    def notify(self, aggregate_second):
        quan = 100 * self.__get_timing_quantile(aggregate_second)
        self.log.debug("Quantile for %s: %s", self.timing, quan)

        self.data.append(quan)
        self.second_window.append(aggregate_second)

        if len(self.data) > self.width :
            self.autostop.add_counting(self)
            self.data.popleft()
            self.second_window.popleft()

            self.deviation = max(self.data) - min(self.data)
            self.log.debug(self.explain())

            if self.deviation < self.height:
                return True
        return False

    def get_rc(self):
        return 33

    def explain(self):
        items = (self.timing, self.width, self.deviation, self.height)
        return "%sms variance for %ss: %.3f%% (<%s%%)" % items


    def widget_explain(self):
        level = self.height / self.deviation
        items = (self.timing, self.width, self.deviation, self.height)
        return ("%sms variance for %ss: %.3f%% (<%s%%)" % items, level)
