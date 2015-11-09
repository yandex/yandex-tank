'''Graphite Uploader plugin that sends aggregated data to Graphite server'''
import logging
import datetime
from pkg_resources import resource_string
from yandextank.plugins.Aggregator import \
    AggregateResultListener, AggregatorPlugin
from yandextank.core import AbstractPlugin
from decode import Decoder, uts
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
        AggregateResultListener.__init__(self)
        self.client = None
        self.decoder = None

    def get_available_options(self):
        return ["address", "port", "tank_tag"]

    def start_test(self):
        self.start_time = datetime.datetime.now()

    def end_test(self, retcode):
        self.end_time = datetime.datetime.now() + datetime.timedelta(minutes=1)
        return retcode

    def configure(self):
        '''Read configuration'''
        self.tank_tag = self.get_option("tank_tag", "none")
        address = self.get_option("address", "localhost")
        port = int(self.get_option("port", "8086"))
        self.client = InfluxDBClient(
            address, port, 'root', 'root', 'mydb')
        grafana_root = self.get_option("grafana_root", "http://localhost/")
        grafana_dashboard = self.get_option("grafana_dashboard", "tank-dashboard")
        uuid=self.core.get_uuid()
        LOG.info(
            "Grafana link: {grafana_root}"
            "dashboard/db/{grafana_dashboard}?var-uuid={uuid}&from=-5m&to=now".format(
                grafana_root=grafana_root,
                grafana_dashboard=grafana_dashboard,
                uuid=uuid,
            )
        )
        self.decoder = Decoder(self.tank_tag, uuid)
        aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        aggregator.add_result_listener(self)

    def aggregate_second(self, data):
        """
        @data: SecondAggregateData
        """
        if self.client:
            points = self.decoder.decode_aggregate(data)
            self.client.write_points(points, 's')

    def monitoring_data(self, data):
        if self.client:
            points = self.decoder.decode_monitoring(data)
            self.client.write_points(points, 's')
