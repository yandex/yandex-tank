'''Report plugin that plots some graphs'''

from Tank.Plugins.Aggregator import AggregateResultListener, AggregatorPlugin
from tankcore import AbstractPlugin
import datetime
import time
import numpy as np
import matplotlib.pyplot as plt

class ReportPlugin(AbstractPlugin, AggregateResultListener):
    '''Graphite data uploader'''
    
    SECTION = 'report'

    @staticmethod
    def get_key():
        return __file__
    
    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.overall = []
        self.timeline = []

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
        aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        aggregator.add_result_listener(self)
            
    def aggregate_second(self, data):
        """
        @data: SecondAggregateData
        """
        ts = int(time.time())
        self.overall.append([ts, data.overall.RPS] + [data.overall.quantiles[key] for key in sorted(data.overall.quantiles)])

    def post_process(self, retcode):
        colors = [
            "#000000",
            "#000000",
            "#DD0000",
            "#DD3800",
            "#DD6E00",
            "#DDAA00",
            "#DDDC00",
            "#A6DD00",
            "#70DD00",
            "#38DD00",
            "#18BB00",
        ]
        legend = [
            "RPS",
            "25",
            "50",
            "75",
            "80",
            "90",
            "95",
            "98",
            "99",
            "100",
        ]
        print self.overall
        overall = np.array(self.overall)
        fig = plt.figure()
        overall_quantiles = fig.add_subplot(111)
        overall_quantiles.grid(True)
        overall_quantiles.plot(overall[:, 0], overall[:, 1], '--')
        [overall_quantiles.fill_between(overall[:, 0], overall[:, i], color=colors[i]) for i in reversed(range(2, len(overall[0])))]
        plt.xlabel("Time")
        plt.ylabel("Quantiles, ms")
        plt.title("RPS and overall quantiles")
        plt.legend(legend, loc='upper left')
        graph_png = self.core.mkstemp(".png", "overall_")
        self.core.add_artifact_file(graph_png)
        plt.savefig(graph_png)
        plt.close()
