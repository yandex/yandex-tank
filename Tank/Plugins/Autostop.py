from Tank.Core import AbstractPlugin
from Tank.Plugins.Aggregator import AggregatorPlugin, AggregateResultListener
from Tank.Plugins.Phantom import PhantomPlugin
from Tank.Utils import CommonUtils
import logging
import re
from Tank.Plugins.ConsoleOnline import AbstractInfoWidget, ConsoleOnlinePlugin

class AutostopPlugin(AbstractPlugin, AggregateResultListener):
    SECTION = 'autostop'

    def __init__(self, core):
        self.log = logging.getLogger(__name__)
        self.core = core
        self.cause_criteria = None
        self.criterias = []
        self.custom_criterias = []
        self.counting = []

    @staticmethod
    def get_key():
        return __file__;

    def get_counting(self):
        return self.counting

    def add_counting(self, obj):
        self.counting += [obj]


    def add_criteria_class(self, criteria_class):
        self.custom_criterias += [criteria_class]
    
    def configure(self):
        aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        aggregator.add_result_listener(self)
        self.criteria_str = " ".join(self.core.get_option(self.SECTION, "autostop", '').split("\n"))
        self.add_criteria_class(AvgTimeCriteria)
        self.add_criteria_class(NetCodesCriteria)
        self.add_criteria_class(HTTPCodesCriteria)
        self.add_criteria_class(UsedInstancesCriteria)

    def prepare_test(self):
        # FIXME: whole parsing is broken now!
        for criteria_str in self.criteria_str.strip().split(")"):
            if not criteria_str: 
                continue
            self.log.debug("Criteria string: %s", criteria_str)
            self.criterias.append(self.create_criteria(criteria_str))
            
        self.log.debug("Criteria object: %s", self.criterias)
    
        try:
            console = self.core.get_plugin_of_type(ConsoleOnlinePlugin)
        except Exception, ex:
            self.log.debug("Console not found: %s", ex)
            console = None
            
        if console:    
            console.add_info_widget(AutostopWidget(self))

    def start_test(self):
        pass

    def end_test(self, retcode):
        return retcode

    def is_test_finished(self):
        if self.cause_criteria:
            self.log.info("Autostop criteria requested test stop: %s", self.cause_criteria.explain())
            return self.cause_criteria.get_rc()
        else:
            return -1

    def create_criteria(self, criteria_str):
        parsed = criteria_str.split("(")
        type_str = parsed[0].strip().lower()
        parsed[1] = parsed[1].split(")")[0].strip()
        
        for criteria_class in self.custom_criterias:
            if criteria_class.get_type_string() == type_str:
                return criteria_class(self, parsed[1])
        raise ValueError("Unsupported autostop criteria type: %s" % criteria_str)
    
    def aggregate_second(self, second_aggregate_data):
        self.counting = []
        for criteria in self.criterias:
            if criteria.notify(second_aggregate_data):
                self.log.debug("Autostop criteria requested test stop: %s", criteria)
                self.cause_criteria = criteria
    

class AbstractCriteria:
    RC_TIME = 21
    RC_HTTP = 22
    RC_NET = 23
    RC_INST = 24
        
    def __init__(self):
        self.log = logging.getLogger(__name__)
        
    def count_matched_codes(self, codes_regex, codes_dict):
        total = 0
        for code, count in codes_dict.items():
            if codes_regex.match(code):
                total += count
        return total
    
    def notify(self, aggregate_second):
        raise RuntimeError("Abstract methods requires overriding")

    def get_rc(self):
        raise RuntimeError("Abstract methods requires overriding")

    def explain(self):
        raise RuntimeError("Abstract methods requires overriding")
    
    def widget_explain(self):
        return (self.explain(), 0)
    
    @staticmethod
    def get_type_string():
        raise RuntimeError("Abstract methods requires overriding")


class AvgTimeCriteria(AbstractCriteria):
    @staticmethod
    def get_type_string():
        return 'time'
    
    def __init__(self, autostop, param_str):
        AbstractCriteria.__init__(self)
        self.seconds_count = 0
        self.rt_limit = CommonUtils.expand_to_milliseconds(param_str.split(',')[0])
        self.seconds_limit = CommonUtils.expand_to_seconds(param_str.split(',')[1])
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
        items = (self.rt_limit, self.seconds_count, self.cause_second.overall.time)
        return "Average response time higher than %sms for %ss, started at: %s" % items

    def widget_explain(self):
        items = (self.rt_limit, self.seconds_count, self.seconds_limit)
        return ("Avg Time >%sms for %s/%ss" % items, float(self.seconds_count) / self.seconds_limit)
    
    
class HTTPCodesCriteria(AbstractCriteria):
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
        self.seconds_limit = CommonUtils.expand_to_seconds(param_str.split(',')[2])
    

    def notify(self, aggregate_second):
        matched_responses = self.count_matched_codes(self.codes_regex, aggregate_second.overall.http_codes)
        if self.is_relative:
            if aggregate_second.overall.RPS:
                matched_responses = float(matched_responses) / aggregate_second.overall.RPS
            else:
                matched_responses = 1
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
        if self.is_relative:
            level_str = str(100 * self.level) + "%"
        else:
            level_str = self.level
        return level_str

    def explain(self):
        items = (self.codes_mask, self.get_level_str(), self.seconds_count, self.cause_second.overall.time)
        return "%s codes count higher than %s for %ss, started at: %s" % items 
    
    def widget_explain(self):
        items = (self.codes_mask, self.get_level_str(), self.seconds_count, self.seconds_limit)
        return ("HTTP %s>%s for %s/%ss" % items, float(self.seconds_count) / self.seconds_limit)

    
class NetCodesCriteria(AbstractCriteria):
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
        self.seconds_limit = CommonUtils.expand_to_seconds(param_str.split(',')[2])
    

    def notify(self, aggregate_second):
        codes = aggregate_second.overall.net_codes.copy()
        if '0' in codes.keys(): codes.pop('0')
        matched_responses = self.count_matched_codes(self.codes_regex, codes)
        if self.is_relative:
            if aggregate_second.overall.RPS:
                matched_responses = float(matched_responses) / aggregate_second.overall.RPS
            else:
                matched_responses = 1
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
        if self.is_relative:
            level_str = str(100 * self.level) + "%"
        else:
            level_str = self.level
        return level_str

    def explain(self):
        items = (self.codes_mask, self.get_level_str(), self.seconds_count, self.cause_second.overall.time)
        return "%s net codes count higher than %s for %ss, started at: %s" % items 
    
    def widget_explain(self):
        items = (self.codes_mask, self.get_level_str(), self.seconds_count, self.seconds_limit)
        return ("Net %s>%s for %s/%ss" % items, float(self.seconds_count) / self.seconds_limit)


class UsedInstancesCriteria(AbstractCriteria):
    @staticmethod
    def get_type_string():
        return 'instances'

    def __init__(self, autostop, param_str):
        AbstractCriteria.__init__(self)
        self.seconds_count = 0
        self.autostop = autostop

        level_str = param_str.split(',')[0].strip()
        if level_str[-1:] == '%':
            self.level = float(level_str[:-1]) / 100
            self.is_relative = True
        else:
            self.level = int(level_str)
            self.is_relative = False
        self.seconds_limit = CommonUtils.expand_to_seconds(param_str.split(',')[1])
        
        phantom = autostop.core.get_plugin_of_type(PhantomPlugin)
        self.threads_limit = phantom.instances
        if not self.threads_limit:
            raise ValueError("Cannot create 'instances' criteria with zero instances limit")
    

    def notify(self, aggregate_second):
        threads = aggregate_second.overall.active_threads
        if self.is_relative:
            threads = float(threads) / self.threads_limit
        if threads > self.level:
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
        return self.RC_INST



    def get_level_str(self):
        if self.is_relative:
            level_str = str(100 * self.level) + "%"
        else:
            level_str = self.level
        return level_str

    def explain(self):
        items = (self.get_level_str(), self.seconds_count, self.cause_second.overall.time)
        return "Testing threads (instances) utilization higher than %s for %ss, started at: %s" % items                 

    def widget_explain(self):
        items = (self.get_level_str(), self.seconds_count, self.seconds_limit)
        return ("Instances >%s for %s/%ss" % items, float(self.seconds_count) / self.seconds_limit)


class AutostopWidget(AbstractInfoWidget):
    def __init__(self, sender):
        AbstractInfoWidget.__init__(self)
        self.owner = sender        
    
    def get_index(self):
        return 100

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
