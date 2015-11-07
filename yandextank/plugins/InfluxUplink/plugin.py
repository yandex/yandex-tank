'''Graphite Uploader plugin that sends aggregated data to Graphite server'''
import logging
import datetime
from pkg_resources import resource_string
from yandextank.plugins.Aggregator import \
    AggregateResultListener, AggregatorPlugin
from yandextank.core import AbstractPlugin
from decode import decode_aggregate, decode_monitoring
from influxdb import InfluxDBClient


LOG = logging.getLogger(__name__)


class InfluxUplinkPlugin(AbstractPlugin, AggregateResultListener):

    '''InfluxDB data uploader'''

    SECTION = 'influx'

    @staticmethod
    def get_key():
        return __file__

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.client = None

    def get_available_options(self):
        return ["address", "port", "prefix", "web_port"]

    def start_test(self):
        start_time = datetime.datetime.now()
        self.start_time = start_time.strftime("%H:%M%%20%Y%m%d")

    def end_test(self, retcode):
        end_time = datetime.datetime.now() + datetime.timedelta(minutes=1)
        self.end_time = end_time.strftime("%H:%M%%20%Y%m%d")
        return retcode

    def configure(self):
        '''Read configuration'''
        self.client = InfluxDBClient(
            'localhost', 8086, 'root', 'root', 'mydb')
        aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        aggregator.add_result_listener(self)

    def aggregate_second(self, data):
        """
        @data: SecondAggregateData
        """
        if self.client:
            points = decode_aggregate(data)
            print("Aggregated:\n%s" % points)
            self.client.write_points(points, 's')

    def monitoring_data(self, data):
        if self.client:
            points = decode_monitoring(data)
            print("Monitoring:\n%s" % points)
            self.client.write_points(points, 's')
