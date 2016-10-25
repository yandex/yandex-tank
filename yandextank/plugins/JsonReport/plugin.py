# TODO: make the next two lines unnecessary
# pylint: disable=line-too-long
# pylint: disable=missing-docstring

import logging
import os

from ..Aggregator import Plugin as AggregatorPlugin
from ..Monitoring import Plugin as MonitoringPlugin
from ..Telegraf import Plugin as TelegrafPlugin
from ...common.interfaces import AbstractPlugin, MonitoringDataListener, AggregateResultListener

logger = logging.getLogger(__name__)  # pylint: disable=C0103


class Plugin(AbstractPlugin, AggregateResultListener, MonitoringDataListener):
    # pylint:disable=R0902
    SECTION = 'json_report'

    def get_available_options(self):
        return []

    def configure(self):
        self.monitoring_logger = self.create_file_logger('monitoring',
                                                         self.get_option('monitoring_log',
                                                                         'monitoring.log'))
        self.aggregator_data_logger = self.create_file_logger('aggregator_data',
                                                              self.get_option('test_data_log',
                                                                              'test_data.log'))
        self.stats_logger = self.create_file_logger('stats',
                                                    self.get_option('test_stats_log',
                                                                    'test_stats.log'))
        self.core.job.subscribe_plugin(self)

    def create_file_logger(self, logger_name, file_name, formatter=None):
        loggr = logging.getLogger(logger_name)
        loggr.setLevel(logging.INFO)
        handler = logging.FileHandler(os.path.join(self.core.artifacts_dir, file_name), mode='w')
        handler.setLevel(logging.INFO)
        if formatter:
            handler.setFormatter(formatter)
        loggr.addHandler(handler)
        loggr.propagate = False
        return loggr

    def on_aggregated_data(self, data, stats):
        """
        @data: aggregated data
        @stats: stats about gun
        """
        self.aggregator_data_logger.info(data)
        self.stats_logger.info(stats)

    def monitoring_data(self, data_list):
        self.monitoring_logger.info(data_list)