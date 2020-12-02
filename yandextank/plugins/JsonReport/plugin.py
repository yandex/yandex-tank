# TODO: make the next two lines unnecessary
# pylint: disable=line-too-long
# pylint: disable=missing-docstring
import json
import logging
import numpy as np
import os

import io

from ...common.interfaces import AbstractPlugin,\
    MonitoringDataListener, AggregateResultListener

logger = logging.getLogger(__name__)  # pylint: disable=C0103


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.generic):
            return obj.item()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return super(NumpyEncoder, self).default(obj)


class Plugin(AbstractPlugin, AggregateResultListener, MonitoringDataListener):
    # pylint:disable=R0902
    SECTION = 'json_report'

    def __init__(self, core, cfg, name):
        super(Plugin, self).__init__(core, cfg, name)
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
        json_string = json.dumps({
            'data': data,
            'stats': stats
        }, cls=NumpyEncoder)
        self.data_and_stats_stream.write('{}\n'.format(json_string).encode('utf-8'))

    def monitoring_data(self, data_list):
        if self.is_telegraf:
            monitoring_data = '{}\n'.format(json.dumps(data_list)).encode('utf-8')
            self.monitoring_stream.write(monitoring_data)
        else:
            [
                self.monitoring_stream.write('{}\n'.format(data.strip()).encode('utf-8')) for data in data_list
                if data
            ]

    def post_process(self, retcode):
        self.data_and_stats_stream.close()
        self.monitoring_stream.close()
        return retcode

    @property
    def is_telegraf(self):
        return True
