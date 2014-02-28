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
        self.overall_quantiles = defaultdict(list)
        self.overall_rps = []
        self.mon_data = {}

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
                    if '_' in key:
                        group, key = key.split('_', 1)
                    else:
                        group = key
                    if group not in host_data:
                        host_data[group] = {}
                    group_data = host_data[group]
                    if key not in group_data:
                        group_data[key] = []
                    try:
                        value = float(value)
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
        ts = int(time.time())
        self.overall_rps.append((ts, data.overall.RPS))
        for key in data.overall.quantiles.keys():
            self.overall_quantiles[key].append((ts, data.overall.quantiles[key]))

    def post_process(self, retcode):
        print self.overall_quantiles
        print self.overall_rps
        print json.dumps(self.mon_data)
        # colors = {
        #     25.0: "#DD0000",
        #     50.0: "#DD3800",
        #     75.0: "#DD6E00",
        #     80.0: "#DDAA00",
        #     90.0: "#DDDC00",
        #     95.0: "#A6DD00",
        #     98.0: "#70DD00",
        #     99.0: "#38DD00",
        #     100.0: "#18BB00",
        # }
        # overall_rps = np.array(self.overall_rps)
        # fig = plt.figure()
        # oq_plot = fig.add_subplot(111)
        # oq_plot.grid(True)
        # oq_keys = sorted(self.overall_quantiles)
        # legend = ["RPS"] + map(lambda x: str(int(x)), oq_keys)
        # oq_plot.plot(overall_rps[:, 0], overall_rps[:, 1], '--')
        # for key in reversed(oq_keys):
        #     quantile = np.array(self.overall_quantiles[key])
        #     oq_plot.fill_between(quantile[:, 0], quantile[:, 1], color=colors[key])
        # # workaround: pyplot can not build a legend for fill_between
        # # so we just draw a bunch of lines here:
        # for key in oq_keys:
        #     quantile = np.array(self.overall_quantiles[key])
        #     oq_plot.plot(quantile[:, 0], quantile[:, 1], color=colors[key])
        # plt.xlabel("Time")
        # plt.ylabel("Quantiles, ms")
        # plt.title("RPS and overall quantiles")
        # oq_plot.legend(legend, loc='upper left')
        # graph_png = self.core.mkstemp(".png", "overall_")
        # self.core.add_artifact_file(graph_png)
        # plt.savefig(graph_png)
        # if self.show_graph:
        #     plt.show()
        # plt.close()
