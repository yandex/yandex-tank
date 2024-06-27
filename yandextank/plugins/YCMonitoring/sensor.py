import re
import json
from datetime import datetime, timezone
from time import time
from queue import Queue

import requests

from logging import getLogger
from yandextank.common.util import observetime
from yandextank.common.monitoring import MonitoringSensorProtocol


LOGGER = getLogger(__name__)


class YCMonitoringSensor(MonitoringSensorProtocol):
    """
    The YCMonitoringSensor class is intended to taking metrics from cloud
    """

    def __init__(
        self,
        panel_name: str,
        api_host: str,
        token: str,
        query: str,
        folder_id: str,
        queue: Queue,
        request_timeout: int,
        priority_labels: list[str],
        ignore_labels: list[str],
    ):
        query, query_folder_id = parse_yc_monitoring_query(query)
        folder_id = folder_id or query_folder_id

        self.panel_name = panel_name
        self.headers = {'Content-type': 'application/json', 'Authorization': f'Bearer {token}'}
        self.params = {'folderId': folder_id}
        self.endpoint = f'https://{api_host}/monitoring/v2/data/read'

        # for some reason YC Monitoring API returns empty response if query contains `folderId=""` param
        # returns no data:    query='"objects_count"{folderId="correctFolderId", service="storage"}'
        # returns valid data: query='"objects_count"{service="storage"}'
        self.data = {
            'query': query,
            'fromTime': datetime.fromtimestamp(time(), tz=timezone.utc).isoformat(),
            'toTime': (datetime.fromtimestamp(time() + 1, tz=timezone.utc)).isoformat(),
            'downsampling': {'gridInterval': 1500},
        }
        self.queue = queue
        self.is_got_some_data_after_parsing = False
        self.request_timeout = request_timeout

        # vector in queue
        self.vector_params = re.findall(r'as_vector\((.*?)\)', query)
        if self.vector_params:
            self.vector_params = self.vector_params[0].split(', ')

        self.priority_labels = priority_labels
        self.ignore_labels = ignore_labels

    def fetch_metrics(self):
        if self.is_got_some_data_after_parsing:
            self.data['fromTime'] = self.data['toTime']
            self.is_got_some_data_after_parsing = False
        self.data['toTime'] = datetime.fromtimestamp(time() + 1, tz=timezone.utc).isoformat()
        self.prepare_data(self.get_data())

    @observetime('YCMonitoringSensor.prepare_data', LOGGER)
    def prepare_data(self, data):
        if isinstance(data, dict) and data.get('metrics'):
            try:
                for idx, sensor_item in enumerate(data['metrics']):
                    if not sensor_item:
                        continue
                    if metrics := self.parse_metrics(sensor_item, idx):
                        self.is_got_some_data_after_parsing = True
                        self.send_metrics(metrics)

            except KeyError as ke:
                LOGGER.warning(f'Wrong data: {data}. {ke}', exc_info=True)
        else:
            LOGGER.warning(f'Wrong data: {data}')

    def parse_metrics(self, metrics: dict, index: int):
        # choosing int or double values
        if metrics['type'] in ['DGAUGE', 'RATE']:
            values_collection = 'doubleValues'
        elif metrics['type'] in ['COUNTER', 'IGAUGE']:
            values_collection = 'int64Values'
        else:
            LOGGER.warning('Unknown metrics type %s', metrics['type'])
            return None

        sensor_name = self.format_sensor(metrics['labels'], index)

        timeseries = metrics.get('timeseries')
        return [
            {
                'sensor': sensor_name,
                'timestamp': tmsp_mill // 1000,
                'value': value,
            }
            for tmsp_mill, value in zip(timeseries['timestamps'], timeseries[values_collection])
            if value != 'NaN'
        ]

    def send_metrics(self, data):
        try:
            self.queue.put(data)
        except (IOError, OSError) as error:
            LOGGER.warning('Sensor %s, send metrics error. %s', data.get('sensor'), error, exc_info=False)

    @observetime('YCMonitoringSensor.get_data', LOGGER)
    def get_data(self, is_first_call: bool = False):
        try:
            response = requests.request(
                'POST',
                self.endpoint,
                headers=self.headers,
                json=self.data,
                params=self.params,
                timeout=self.request_timeout,
            )

            response.raise_for_status()
        except ConnectionError as e:
            if is_first_call:
                raise ConnectionError('After first call got connection error, so you should not add sensors') from e
            LOGGER.exception('Connection error during request')
        except Exception:
            LOGGER.exception('request to YC Cloud Monitoring API failed')
        else:
            try:
                return json.loads(response.text)
            except json.JSONDecodeError as e:
                LOGGER.error('YCMonitoringSensor json parse error: %s', e, exc_info=False)

    def get_sensors(self):
        sensors = set()
        data = self.get_data(is_first_call=True)
        if isinstance(data, dict) and data.get('metrics'):
            for idx, metric in enumerate(data['metrics']):
                sensors.add(self.format_sensor(metric['labels'], idx))
        return sensors

    def format_sensor(self, labels: dict[str, str], index: int) -> str:
        line_name = None
        if not self.vector_params:
            # priority first
            for label in self.priority_labels:
                if label in labels:
                    line_name = labels[label]

            # other labels
            if not line_name:
                parts = []
                for label, value in labels.items():
                    if label in self.ignore_labels:
                        continue
                    else:
                        parts.append(value)
                line_name = '; '.join(parts)
        else:
            line_name = ''.join(['p', self.vector_params[index]])

        return self.panel_name.replace('_', '-') + '_' + line_name


def parse_yc_monitoring_query(query: str) -> tuple[str, str]:
    quote = '("|\')?'
    folderId = '([a-zA-Z0-9._-]+)'
    tail = '\\s*,?\\s*'
    m = re.search(f'folderId={quote}{folderId}{quote}{tail}', query)
    if not m:
        return query, ''

    return query.replace(m.group(0), ''), m.group(2)
