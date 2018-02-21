# coding=utf-8
# TODO: make the next two lines unnecessary
# pylint: disable=line-too-long
# pylint: disable=missing-docstring
import logging
import sys
import datetime

from uuid import uuid4
from builtins import str
from influxdb import InfluxDBClient

from ...common.interfaces import AbstractPlugin, \
    MonitoringDataListener, AggregateResultListener
from .decoder import Decoder

logger = logging.getLogger(__name__)  # pylint: disable=C0103


def chop(data_list, chunk_size):
    if sys.getsizeof(str(data_list)) <= chunk_size:
        return [data_list]
    elif len(data_list) == 1:
        logger.warning("Too large piece of Telegraf data. Might experience upload problems.")
        return [data_list]
    else:
        mid = len(data_list) / 2
        return chop(data_list[:mid], chunk_size) + chop(data_list[mid:], chunk_size)


class Plugin(AbstractPlugin, AggregateResultListener,
             MonitoringDataListener):

    SECTION = 'influx'

    def __init__(self, core, cfg, cfg_updater):
        AbstractPlugin.__init__(self, core, cfg, cfg_updater)
        self.tank_tag = self.get_option("tank_tag")
        address = self.get_option("address")
        port = self.get_option("port")
        self.client = InfluxDBClient(
            address,
            port,
            username=self.get_option("username"),
            password=self.get_option("password"),
            database=self.get_option("database"),
        )
        grafana_root = self.get_option("grafana_root")
        grafana_dashboard = self.get_option("grafana_dashboard")
        uuid = str(uuid4())
        logger.info(
            "Grafana link: {grafana_root}"
            "dashboard/db/{grafana_dashboard}?var-uuid={uuid}&from=-5m&to=now".format(
                grafana_root=grafana_root,
                grafana_dashboard=grafana_dashboard,
                uuid=uuid,
            )
        )
        self.decoder = Decoder(self.tank_tag, uuid)

    def start_test(self):
        self.start_time = datetime.datetime.now()

    def end_test(self, retcode):
        self.end_time = datetime.datetime.now() + datetime.timedelta(minutes=1)
        return retcode

    def prepare_test(self):
        self.core.job.subscribe_plugin(self)

    def on_aggregated_data(self, data, stats):
        if self.client:
            points = self.decoder.decode_aggregate(data, stats)
            self.client.write_points(points, 's')

    def monitoring_data(self, data_list):
        if self.client:
            if len(data_list) > 0:
                [
                    self._send_monitoring(chunk)
                    for chunk in chop(data_list, self.get_option("chunk_size"))
                ]

    def _send_monitoring(self, data):
        points = self.decoder.decode_monitoring(data)
        self.client.write_points(points, 's')
