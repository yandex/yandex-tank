# TODO: make the next two lines unnecessary
# pylint: disable=line-too-long
# pylint: disable=missing-docstring
import json
import logging
import os

from ...common.interfaces import AbstractPlugin,\
    MonitoringDataListener, AggregateResultListener

logger = logging.getLogger(__name__)  # pylint: disable=C0103


class Plugin(AbstractPlugin, AggregateResultListener, MonitoringDataListener):
    # pylint:disable=R0902
    SECTION = 'json_report'

    def __init__(self, core):
        super(Plugin, self).__init__(core)
        self._is_telegraf = None

    def get_available_options(self):
        return ['monitoring_log', 'test_data_log', 'test_stats_log']

    def configure(self):
        self.monitoring_logger = self.create_file_logger(
            'monitoring', self.get_option('monitoring_log', 'monitoring.log'))
        self.aggregator_data_logger = self.create_file_logger(
            'aggregator_data',
            self.get_option('test_data_log', 'test_data.log'))
        self.core.job.subscribe_plugin(self)

    def create_file_logger(self, logger_name, file_name, formatter=None):
        loggr = logging.getLogger(logger_name)
        loggr.setLevel(logging.INFO)
        handler = logging.FileHandler(
            os.path.join(self.core.artifacts_dir, file_name), mode='w')
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
        self.aggregator_data_logger.info(
            json.dumps({
                'data': data,
                'stats': stats
            }))

    def monitoring_data(self, data_list):
        if self.is_telegraf:
            self.monitoring_logger.info(json.dumps(data_list))
        else:
            [
                self.monitoring_logger.info(data.strip()) for data in data_list
                if data
            ]

    @property
    def is_telegraf(self):
        if self._is_telegraf is None:
            self._is_telegraf = 'Telegraf' in self.core.job.monitoring_plugin.__module__
        return self._is_telegraf
