import os
from queue import Queue

import logging
from yandextank.common.interfaces import MonitoringPlugin
from yandextank.common.monitoring import MonitoringPanel, DefaultCollector
from yandextank.common.util import expand_to_seconds
from yandextank.plugins.YCMonitoring.sensor import YCMonitoringSensor

LOGGER = logging.getLogger(__name__)


def as_list(value) -> list | None:
    if value is None or isinstance(value, list):
        return value
    return [value]


class Plugin(MonitoringPlugin):
    def __init__(self, core, cfg, name):
        super(Plugin, self).__init__(core, cfg, name)
        self.timeout = expand_to_seconds(self.get_option('timeout'))
        self.poll_interval = expand_to_seconds(self.get_option('poll_interval'))
        self.request_timeout = expand_to_seconds(self.get_option('request_timeout'))

    def prepare_test(self):
        token = None
        token_option = self.get_option('token')
        if token_option == 'LOADTESTING_YC_TOKEN':
            token = os.environ.get('LOADTESTING_YC_TOKEN')
        else:
            try:
                with open(token_option, 'r') as tfile:
                    token = tfile.read().strip('\n')
            except (OSError, IOError):
                error = f"YCMonitoring plugin: Authorization token is not set! File {self.get_option('token')} is not found or can't be read."
                LOGGER.warning(error, exc_info=True)

        if token:
            self.collector = DefaultCollector(logger=LOGGER, timeout=self.timeout, poll_interval=self.poll_interval)
            api_host = self.get_option('api_host')
            for panel_name, query_data in self.get_option('panels').items():
                queue = Queue()
                group_name = query_data.get('group_name') or api_host
                panel = MonitoringPanel(group_name, self.timeout, queue)
                senset = set()
                for query in query_data.get('queries'):
                    sensor = YCMonitoringSensor(
                        panel_name,
                        api_host,
                        token,
                        query,
                        query_data.get('folder_id') or os.environ.get('LOADTESTING_FOLDER_ID'),
                        panel.queue,
                        self.request_timeout,
                        as_list(self.get_option('priority_labels')),
                        as_list(self.get_option('ignore_labels')),
                    )
                    try:
                        senset.update(sensor.get_sensors())
                        self.collector.add_sensor(sensor)
                    except ConnectionError:
                        LOGGER.warning(f'ConnectionError when trying to get sensors with query: {query}', exc_info=True)
                panel.add_sensors(senset)
                self.collector.add_panel(panel)
        else:
            LOGGER.warning('YC Token not found')
