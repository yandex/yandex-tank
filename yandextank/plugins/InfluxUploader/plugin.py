# coding=utf-8
# TODO: make the next two lines unnecessary
# pylint: disable=line-too-long
# pylint: disable=missing-docstring
import datetime
import logging
import sys
from uuid import uuid4

from builtins import str
from influxdb import InfluxDBClient

from .decoder import Decoder
from ...common.interfaces import AbstractPlugin, \
    MonitoringDataListener, AggregateResultListener

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

    def __init__(self, core, cfg, name):
        AbstractPlugin.__init__(self, core, cfg, name)
        self.tank_tag = self.get_option("tank_tag")
        self.prefix_measurement = self.get_option("prefix_measurement")
        self._client = None
        self.start_time = None
        self.end_time = None
        self.decoder = Decoder(
            self.tank_tag,
            str(uuid4()),
            self.get_option("custom_tags"),
            self.get_option("labeled"),
            self.get_option("histograms"),
        )

    @property
    def client(self):
        if not self._client:
            self._client = InfluxDBClient(
                self.get_option("address"),
                self.get_option("port"),
                ssl=self.get_option("ssl"),
                verify_ssl=self.get_option("verify_ssl"),
                path=self.get_option("path"),
                username=self.get_option("username"),
                password=self.get_option("password"),
                database=self.get_option("database"),
            )
        return self._client

    def prepare_test(self):
        self.core.job.subscribe_plugin(self)

    def start_test(self):
        self.start_time = datetime.datetime.now()

    def end_test(self, retcode):
        self.end_time = datetime.datetime.now() + datetime.timedelta(minutes=1)
        return retcode

    def on_aggregated_data(self, data, stats):
        self.client.write_points(
            self.decoder.decode_aggregates(data, stats, self.prefix_measurement),
            's'
        )

    def monitoring_data(self, data_list):
        if len(data_list) > 0:
            [
                self._send_monitoring(chunk)
                for chunk in chop(data_list, self.get_option("chunk_size"))
            ]

    def _send_monitoring(self, data):
        self.client.write_points(
            self.decoder.decode_monitoring(data),
            's'
        )

    def set_uuid(self, id_):
        self.decoder.tags['uuid'] = id_
