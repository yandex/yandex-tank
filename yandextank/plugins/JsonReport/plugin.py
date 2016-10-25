# TODO: make the next two lines unnecessary
# pylint: disable=line-too-long
# pylint: disable=missing-docstring

import logging

from ..Aggregator import Plugin as AggregatorPlugin
from ..Monitoring import Plugin as MonitoringPlugin
from ..Telegraf import Plugin as TelegrafPlugin
from ...common.interfaces import AbstractPlugin, MonitoringDataListener, AggregateResultListener

logger = logging.getLogger(__name__)  # pylint: disable=C0103


class Plugin(AbstractPlugin, AggregateResultListener, MonitoringDataListener):
    # pylint:disable=R0902
    """ Yandex Overload analytics service client (https://overload.yandex.net) """
    SECTION = 'json_report'

    def get_available_options(self):
        return []

    def configure(self):
        # try:
        #     aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        # except KeyError:
        #     logger.debug("Aggregator plugin not found", exc_info=True)
        # else:
        #     aggregator.add_result_listener(self)
        #
        # try:
        #     self.mon = self.core.get_plugin_of_type(TelegrafPlugin)
        # except KeyError:
        #     logger.debug("Telegraf plugin not found:", exc_info=True)
        #     try:
        #         self.mon = self.core.get_plugin_of_type(MonitoringPlugin)
        #     except KeyError:
        #         logger.debug("Monitoring plugin not found:", exc_info=True)
        #
        # if self.mon and self.mon.monitoring:
        #     self.mon.monitoring.add_listener(self)
        self.core.job.subscribe_plugin(self)

    def on_aggregated_data(self, data, stats):
        """
        @data: aggregated data
        @stats: stats about gun
        """
        print(data)
        print(stats)

    def monitoring_data(self, data_list):
        print(data_list)