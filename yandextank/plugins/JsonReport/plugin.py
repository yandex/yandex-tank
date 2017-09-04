# TODO: make the next two lines unnecessary
# pylint: disable=line-too-long
# pylint: disable=missing-docstring
import json
import logging
import os

import io

from ...common.interfaces import AbstractPlugin,\
    MonitoringDataListener, AggregateResultListener

logger = logging.getLogger(__name__)  # pylint: disable=C0103


class Plugin(AbstractPlugin, AggregateResultListener, MonitoringDataListener):
    # pylint:disable=R0902
    SECTION = 'json_report'

    def __init__(self, core, cfg, cfg_updater):
        super(Plugin, self).__init__(core, cfg, cfg_updater)
        self.monitoring_stream = io.open(os.path.join(self.core.artifacts_dir,
                                                      self.get_option('monitoring_log')),
                                         mode='wb')
        self.data_and_stats_stream = io.open(os.path.join(self.core.artifacts_dir,
                                                          self.get_option('test_data_log')),
                                             mode='wb')
        self._is_telegraf = None

    def get_available_options(self):
        return ['monitoring_log', 'test_data_log']

    def configure(self):
        self.core.job.subscribe_plugin(self)

    def on_aggregated_data(self, data, stats):
        """
        @data: aggregated data
        @stats: stats about gun
        """
        self.data_and_stats_stream.write(
            '%s\n' % json.dumps({
                'data': data,
                'stats': stats
            }))

    def monitoring_data(self, data_list):
        if self.is_telegraf:
            self.monitoring_stream.write('%s\n' % json.dumps(data_list))
        else:
            [
                self.monitoring_stream.write('%s\n' % data.strip()) for data in data_list
                if data
            ]

    def post_process(self, retcode):
        self.data_and_stats_stream.close()
        self.monitoring_stream.close()
        return retcode

    @property
    def is_telegraf(self):
        if self._is_telegraf is None:
            self._is_telegraf = 'Telegraf' in self.core.job.monitoring_plugin.__module__
        return self._is_telegraf
