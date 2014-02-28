'''Report plugin that plots some graphs'''

from Tank.Plugins.Aggregator import AggregateResultListener, AggregatorPlugin
from Tank.Plugins.Monitoring import MonitoringPlugin
from Tank.MonCollector.collector import MonitoringDataListener, MonitoringDataDecoder
from tankcore import AbstractPlugin
import datetime
import time
import numpy as np
import matplotlib.pyplot as plt
import json
from collections import defaultdict

class ReportPlugin(AbstractPlugin, AggregateResultListener, MonitoringDataListener):
    '''Graphite data uploader'''
    
    SECTION = 'report'

    @staticmethod
    def get_key():
        return __file__
    
    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.decoder = MonitoringDataDecoder()
        self.mon_data = {}
        def create_storage():
            return {
                'avg': defaultdict(list),
                'quantiles': defaultdict(list),
                'threads': {
                    'active_threads': []
                },
                'rps': {
                    'RPS': []
                },
            }
        self.overall = create_storage()
        self.cases = defaultdict(create_storage)

    def monitoring_data(self, data_string):
        self.log.debug("Mon report data: %s", data_string)
        for line in data_string.splitlines():
            if not line.strip():
                continue
            
            def append_data(host, ts, data):
                if host not in self.mon_data:
                    self.mon_data[host] = {}
                host_data = self.mon_data[host]
                for key, value in data.iteritems():
                    try:
                        value = float(value)
                        if '_' in key:
                            group, key = key.split('_', 1)
                        else:
                            group = key
                        if group not in host_data:
                            host_data[group] = {}
                        group_data = host_data[group]
                        if key not in group_data:
                            group_data[key] = []
                        group_data[key].append((int(ts), value))
                    except ValueError:
                        pass
            host, data, _, ts = self.decoder.decode_line(line)
            append_data(host, ts, data)
            
    def get_available_options(self):
        return []

    def start_test(self):
        start_time = datetime.datetime.now()
        self.start_time = start_time.strftime("%H:%M%%20%Y%m%d")

    def end_test(self, retcode):
        end_time = datetime.datetime.now() + datetime.timedelta(minutes = 1)
        self.end_time = end_time.strftime("%H:%M%%20%Y%m%d")

    def configure(self):
        '''Read configuration'''
        self.show_graph = self.get_option("show_graph", "")
        aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        aggregator.add_result_listener(self)
        try:
            self.mon = self.core.get_plugin_of_type(MonitoringPlugin)
            if self.mon.monitoring:
                self.mon.monitoring.add_listener(self)
        except KeyError:
            self.log.warning("No monitoring module, monitroing report disabled")
            
    def aggregate_second(self, data):
        """
        @data: SecondAggregateData
        """
        ts = int(time.mktime(data.time.timetuple()))
        def add_aggreagted_second(data_item, storage):
            data_dict = data_item.__dict__
            avg = storage['avg']
            for key in ["avg_connect_time", "avg_send_time", "avg_latency", "avg_receive_time"]:
                avg[key].append((ts, data_dict.get(key, None)))
            quantiles = storage['quantiles']
            for key, value in data_item.quantiles.iteritems():
                quantiles[key].append((ts, value))
        add_aggreagted_second(data.overall, self.overall)
        for case, case_data in data.cases.iteritems():
            add_aggreagted_second(case_data, self.cases[case])

    def post_process(self, retcode):
        results = {
            'overall': self.overall,
            'cases': self.cases,
            'monitoring': self.mon_data,
        }
        print json.dumps(results)

