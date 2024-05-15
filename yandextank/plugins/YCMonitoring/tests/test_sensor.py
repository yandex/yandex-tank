import pytest
import json
import os

from yandextank.common.util import get_test_path
from yandextank.plugins.YCMonitoring.sensor import YCMonitoringSensor, parse_yc_monitoring_query


SENSOR = YCMonitoringSensor(
    'example',
    '',
    '',
    '',
    '',
    None,
    10,
    priority_labels=['cpu_name', 'label'],
    ignore_labels=[
        'service',
        'resource_type',
        'device',
        'interface_number',
        'source_metric',
        'subcluster_name',
        'shard',
        'dc',
    ],
)


@pytest.mark.parametrize(
    'json_file_name, formated_sensors',
    [
        ('COUNTER.json', {'example_load-mock-kuber; kube-proxy-bb6kp; kube-system'}),
        (
            'DGAUGE.json',
            {
                'example_replica; test_host.net; postgresql_loadtesting',
                'example_primary; test_host_2.net; postgresql_loadtesting',
            },
        ),
        (
            'IGAUGE.json',
            {'example_test1-instance-group', 'example_test2-instance-group'},
        ),
        (
            'RATE.json',
            {'example_dqtcr5464dbkv1s1rtrt; instance_example; 5', 'example_dqtcr5464dbkv1s1rtrt; instance_example; 2'},
        ),
    ],
)
def test_format_sensors(json_file_name: str, formated_sensors: set):
    with open(
        os.path.join(get_test_path(), f'yandextank/plugins/YCMonitoring/tests/{json_file_name}'), 'r'
    ) as json_file:
        data = json.load(json_file)

    sensors = set()
    if isinstance(data, dict) and data.get('metrics'):
        for idx, metric in enumerate(data['metrics']):
            sensors.add(SENSOR.format_sensor(metric['labels'], idx))
    assert sensors == formated_sensors


@pytest.mark.parametrize(
    'query, expected_query, folder_id',
    [
        ('"objects_count"{service="storage"}', '"objects_count"{service="storage"}', ''),
        (
            '"objects_count"{folderId=\'hahahaha\' , service="storage"}',
            '"objects_count"{service="storage"}',
            'hahahaha',
        ),
        ('"objects_count"{folderId=hahahaha  , service="storage"}', '"objects_count"{service="storage"}', 'hahahaha'),
        (
            'cpu_utilization{folderId="hahahaha", service=\'compute\', resource_type=\'vm\', resource_id=\'resource-rc1b-1\'}',
            'cpu_utilization{service=\'compute\', resource_type=\'vm\', resource_id=\'resource-rc1b-1\'}',
            'hahahaha',
        ),
        (
            'alias(series_sum("instance", "app.request_latency_ms_count"{folderId="asldkfjh123", service="custom", handle="/path"}), "{{instance}}")',
            'alias(series_sum("instance", "app.request_latency_ms_count"{service="custom", handle="/path"}), "{{instance}}")',
            'asldkfjh123',
        ),
    ],
)
def test_parse_yc_monitoring_query(query, expected_query, folder_id):
    actual_query, actual_folder_id = parse_yc_monitoring_query(query)
    assert actual_query == expected_query
    assert actual_folder_id == folder_id
