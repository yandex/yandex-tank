from Tank import Utils
from Tank.Core import AbstractPlugin
import datetime
import logging

class AggregateResultListener:
    def aggregate_second(self, second_aggregate_data):
        raise TypeError("Abstract method needs to be overridden")
    

class AggregatorPlugin(AbstractPlugin):

    default_time_periods = "1 2 3 4 5 6 7 8 9 10 20 30 40 50 60 70 80 90 100 150 200 250 300 350 400 450 500 600 650 700 750 800 850 900 950 1s 1500 2s 2500 3s 3500 4s 4500 5s 5500 6s 6500 7s 7500 8s 8500 9s 9500 10s 11s"

    SECTION = 'aggregator'
    OPTION_STEPS = 'steps'
    OPTION_DETAILED_FIELD = "detailed_time"
    
    @staticmethod
    def get_key():
        return __file__
        
    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.process = None
        self.second_data_listeners = []
        self.preproc_out_offset = 0
        self.buffer = []
        self.second_data_draft = []
        self.preproc_out_filename = None
        self.cumulative_data = SecondAggregateDataTotalItem()
        self.reader = None
    
    def configure(self):
        periods = self.get_option("time_periods", self.default_time_periods).split(" ")
        self.time_periods = " ".join([ str(Utils.expand_to_milliseconds(x)) for x in periods ])
        self.core.set_option(self.SECTION, "time_periods", self.time_periods)
        self.detailed_field = self.get_option(self.OPTION_DETAILED_FIELD, 'interval_real')
        self.preproc_steps = self.get_option(self.OPTION_STEPS, "")

    def prepare_test(self):
        pass
    
    
    def start_test(self):
        if not self.reader:
            self.log.warning("No one set reader for aggregator yet")
    
    def read_samples(self, limit=0, force=False):
        if self.reader:
            self.reader.check_open_files()
            data = self.reader.get_next_sample(force)
            count = 0
            while data and (limit < 1 or count < limit):
                self.notify_listeners(data)
                data = self.reader.get_next_sample(force)
        
    def is_test_finished(self):
        self.read_samples(5)                    
        return -1

    def end_test(self, retcode):
        self.read_samples(force=True)
        return retcode                
        
    def add_result_listener(self, listener):
        self.second_data_listeners += [listener]
    
    def notify_listeners(self, data):
        for listener in self.second_data_listeners:
            listener.aggregate_second(data)
    
    def get_timeout(self):
        return self.time_periods.split(' ')[-1:][0]

class SecondAggregateData:
    def __init__(self, cimulative_item):
        self.cases = {}
        self.time = None
        # @type self.overall: SecondAggregateDataItem
        self.overall = SecondAggregateDataItem()
        self.cumulative = cimulative_item

class SecondAggregateDataItem:
    def parse_singles(self, line):
        if line.startswith(self.T_OVERALL):
            self.overall = int(line.strip()[len(self.T_OVERALL):])
        if line.startswith(self.T_CASE):
            self.case = line.strip()[len(self.T_CASE):]
        if line.startswith(self.T_TIMESTAMP):
            self.time = datetime.datetime.strptime(line.strip()[len(self.T_TIMESTAMP):], "%Y%m%d%H%M%S")
        if line.startswith(self.T_REQPS):
            self.planned_requests = int(line.strip()[len(self.T_REQPS):])
        if line.startswith(self.T_TASKS):
            self.active_threads = int(line.strip()[len(self.T_TASKS):])
        if line.startswith(self.T_INPUT):
            self.input = int(line.strip()[len(self.T_INPUT):])
        if line.startswith(self.T_OUTPUT):
            self.output = int(line.strip()[len(self.T_OUTPUT):])
        if line.startswith(self.T_SELFLOAD):
            selfload = line.strip()[len(self.T_SELFLOAD):]
            if selfload != "0":
                self.selfload = float(selfload[:-1])
            else: 
                self.selfload = 0


    def parse_avg_times(self, line):
        if line.startswith(self.T_CONNECT):
            self.avg_connect_time = float(line.strip()[len(self.T_CONNECT):]) / 1000
        if line.startswith(self.T_SEND):
            self.avg_send_time = float(line.strip()[len(self.T_SEND):]) / 1000
        if line.startswith(self.T_LATENCY):
            self.avg_latency = float(line.strip()[len(self.T_LATENCY):]) / 1000
        if line.startswith(self.T_RECEIVE):
            self.avg_receive_time = float(line.strip()[len(self.T_RECEIVE):]) / 1000
        if line.startswith(self.T_AVG_RT):
            self.avg_response_time = float(line.strip()[len(self.T_AVG_RT):]) / 1000


    def parse_distributions(self, line):
        if line.startswith(self.T_HTTP_CODE):
            times_line = line.strip()[len(self.T_HTTP_CODE):].strip()
            parts = times_line.split(":")
            self.http_codes[parts[0]] = int(parts[1])

        if line.startswith(self.T_NET_CODE):
            times_line = line.strip()[len(self.T_NET_CODE):].strip()
            parts = times_line.split(":")
            self.net_codes[parts[0]] = int(parts[1])

        if line.startswith(self.T_TIMES):
            times_line = line.strip()[len(self.T_TIMES):].strip()
            parts = times_line.split(":")
            interval = parts[0].split('-')
            self.times_dist += [{"from": int(interval[0]), "to": int(interval[1]), "count": int(parts[1])}]

    
    def parse_quantiles(self, line):
        if self.T_DISPERSION in line:
            line = line.strip()
            dis = line[line.find(self.T_DISPERSION) + len(self.T_DISPERSION):]
            self.dispersion = float(dis)
        
        if "_q" in line:
            parts = line.split("=")
            level_parts = parts[0].split("_q")
            self.quantiles[level_parts[1]] = int(parts[1]) / 1000
    
    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.case = None
        self.planned_requests = None
        self.active_threads = 0
        self.selfload = None
        self.RPS = None
        self.http_codes = {}
        self.net_codes = {}
        self.times_dist = []
        self.quantiles = {}
        self.dispersion = None
        self.input = None
        self.avg_connect_time = 0
        self.avg_send_time = 0
        self.avg_latency = 0
        self.avg_receive_time = 0
        self.avg_response_time = 0

class SecondAggregateDataTotalItem:
    def __init__(self):
        self.avg_connect_time = 0
        self.avg_send_time = 0
        self.avg_latency = 0
        self.avg_receive_time = 0
        self.avg_response_time = 0
        self.total_count = 0
        self.times_dist = {}
    
    def add_data(self, overall_item):
        for time_item in overall_item.times_dist:
            self.total_count += time_item['count']
            if time_item['from'] in self.times_dist.keys():
                self.times_dist[time_item['from']]['count'] += time_item['count']
            else:
                self.times_dist[time_item['from']] = time_item



# ===============================================================
class AbstractReader:
    '''
    Parent class for all source reading adapters
    '''
    def __init__(self, owner):
        self.owner = owner
        self.log = logging.getLogger(__name__)

    def check_open_files(self):
        pass

    def get_next_sample(self, force):
        pass


    def append_sample(self, result, item):
        (marker, threads, overall_rt, http_code, net_code, sent_bytes, received_bytes, connect, send, latency, receive, accuracy) = item
        result.case = marker
        result.active_threads = threads
        result.planned_requests = None
        result.RPS += 1
        result.http_codes = {}
        result.net_codes = {}
        result.times_dist = []
        
        result.quantiles = {}
        result.dispersion = None

        result.input += received_bytes
        result.output += sent_bytes
        
        result.avg_connect_time += connect 
        result.avg_send_time += send 
        result.avg_latency += latency
        result.avg_receive_time += receive
        result.avg_response_time += overall_rt
        result.selfload += accuracy

    
    
    def parse_second(self, next_time, data):
        self.log.debug("Parsing second: %s", next_time)
        result = SecondAggregateData(self.cumulative)
        result.time = datetime.datetime.fromtimestamp(next_time)
        for item in data:
            self.append_sample(result.overall, item)
            marker = item[0]
            if marker:
                if not marker in result.cases.keys:
                    result.cases[marker] = SecondAggregateDataItem()
                self.append_sample(result.cases[marker], item)
            
        return result
    

