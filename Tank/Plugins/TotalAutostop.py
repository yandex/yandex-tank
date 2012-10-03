from Tank.Plugins.Aggregator import AggregateResultListener
from Tank.Plugins.Autostop import AbstractCriteria, AutostopPlugin
from collections import deque
from tankcore import AbstractPlugin
import re
import tankcore

class TotalAutostopPlugin(AbstractPlugin, AggregateResultListener):
    SECTION='autostop'
    @staticmethod
    def get_key():
        return __file__;

    def configure(self):
        autostop = self.core.get_plugin_of_type(AutostopPlugin)
        autostop.add_criteria_class(TotalFracTimeCriteria)
        autostop.add_criteria_class(TotalHTTPCodesCriteria)
        autostop.add_criteria_class(TotalNetCodesCriteria)
        autostop.add_criteria_class(TotalNegativeHTTPCodesCriteria)

    def prepare_test(self):
        pass

    def start_test(self):
        pass

    def end_test(self, retcode):
        pass

class TotalFracTimeCriteria(AbstractCriteria):
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

    def notify(self, aggregate_second):
        failcnt = 0
        cnt = 0
        for i in reversed(aggregate_second.overall.times_dist):
            if i['from'] >= self.rt_limit : failcnt += i['count'];
            cnt += i['count']
        value = float(failcnt) / cnt
        self.data.append(value)
        if len(self.data) > self.seconds_limit:
            self.data.popleft()
        self.real_frac = float(sum(self.data)) /  len(self.data) * 100
        if self.real_frac >= float(self.frac) and len(self.data) >= self.seconds_limit:
            self.cause_second = aggregate_second
            self.log.debug(self.explain())
            self.autostop.add_counting(self)
            return True
            #raise ValueError("Hakuna Matata!")
        return False

    def get_rc(self):
        return self.RC_TIME

    def explain(self):
        items = (round(self.real_frac, 2), self.rt_limit, self.seconds_limit, self.cause_second.time)
        return "%s%% responses times higher than %sms for %ss, ended at: %s" % items

    def widget_explain(self):
        items = (round(self.real_frac, 2), self.rt_limit, self.seconds_limit)
        return ("%s%% Times >%sms for %ss" % items, self.real_frac)

class TotalHTTPCodesCriteria(AbstractCriteria):
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
        if len(self.data) > self.seconds_limit :    self.data.popleft()

        # based on moment
        # for i in self.data:
        #     if i < self.level:  return False
        # self.cause_second = aggregate_second
        # self.log.debug(self.explain())
        # self.autostop.add_counting(self)
        # return True

#        based on avg
        x = 1
        if self.is_relative : x = len(self.data)
        if (sum(self.data) / x) >= self.level and len(self.data) >= self.seconds_limit:
                self.cause_second = aggregate_second
                self.log.debug(self.explain())
                self.autostop.add_counting(self)
                return True
        return False

    def get_rc(self):
        return self.RC_HTTP

    def get_level_str(self):
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
        return "%s codes count higher than %s for %ss, started at: %s" % items 
    
    def widget_explain(self):
        if self.is_relative:
            items = (self.codes_mask, self.get_level_str(), self.seconds_limit)
            return ("HTTP %s>%s for %ss" % items, sum(self.data))
        items = (self.codes_mask, self.get_level_str(), self.seconds_limit)
        return ("HTTP %s>%s for %ss" % items, 1.0)

class TotalNetCodesCriteria(AbstractCriteria):
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
        if '0' in codes.keys(): codes.pop('0')
        matched_responses = self.count_matched_codes(self.codes_regex, codes)
        if self.is_relative:
            if aggregate_second.overall.RPS:
                matched_responses = float(matched_responses) / aggregate_second.overall.RPS * 100
                self.log.debug("Net codes matching mask %s: %s%%/%s", self.codes_mask, round(matched_responses, 2), self.get_level_str())
            else:
                matched_responses = 1
        else : self.log.debug("Net codes matching mask %s: %s/%s", self.codes_mask, matched_responses, self.get_level_str())

        self.data.append(matched_responses)
        if len(self.data) > self.seconds_limit : self.data.popleft()

        x = 1
        if self.is_relative : x = len(self.data)
        if (sum(self.data) / x) >= self.level and len(self.data) >= self.seconds_limit:
            self.cause_second = aggregate_second
            self.log.debug(self.explain())
            self.autostop.add_counting(self)
            return True
        return False

    def get_rc(self):
        return self.RC_NET

    def get_level_str(self):
        if self.is_relative:
            level_str = str(self.level) + "%"
        else:
            level_str = str(self.level)
        return level_str

    def explain(self):
        if self.is_relative:
            items = (self.codes_mask, self.get_level_str(), self.seconds_limit, self.cause_second.time)
            return "%s net codes count higher than %s for %ss, ended at: %s" % items 
        items = (self.codes_mask, self.get_level_str(), self.seconds_limit, self.cause_second.time)
        return "%s net codes count higher than %s for %ss, started at: %s" % items 
    
    def widget_explain(self):
        if self.is_relative:
            items = (self.codes_mask, self.get_level_str(), self.seconds_limit)
            return ("Net %s>%s for %ss" % items, self.level)
        items = (self.codes_mask, self.get_level_str(), self.seconds_limit)
        return ("Net %s>%s for %ss" % items, self.level)

class TotalNegativeHTTPCodesCriteria(AbstractCriteria):
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
        if len(self.data) > self.seconds_limit :    self.data.popleft()

        x = 1
        if self.is_relative : x = len(self.data)
        if (sum(self.data) / x) >= self.level and len(self.data) >= self.seconds_limit:
            self.cause_second = aggregate_second
            self.log.debug(self.explain())
            self.autostop.add_counting(self)
            return True
        return False

    def get_rc(self):
        return self.RC_HTTP

    def get_level_str(self):
        if self.is_relative:
            level_str = str(self.level) + "%"
        else:
            level_str = self.level
        return level_str

    def explain(self):
        if self.is_relative:
            items = (self.codes_mask, self.get_level_str(), self.seconds_limit, self.cause_second.time)
            return "Not %s codes count higher than %s for %ss, ended at: %s" % items
        items = (self.codes_mask, self.get_level_str(), self.seconds_limit, self.cause_second.time)
        return "Not %s codes count higher than %s for %ss, started at: %s" % items 
    
    def widget_explain(self):
        if self.is_relative:
            items = (self.codes_mask, self.get_level_str(), self.seconds_limit)
            return ("HTTP not %s>%s for %ss" % items, sum(self.data))
        items = (self.codes_mask, self.get_level_str(), self.seconds_limit)
        return ("HTTP not %s>%s for %ss" % items, 1.0)
