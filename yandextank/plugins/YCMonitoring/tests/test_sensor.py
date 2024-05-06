import pytest
import json
import os

from yandextank.common.util import get_test_path
from yandextank.plugins.YCMonitoring.sensor import YCMonitoringSensor


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
