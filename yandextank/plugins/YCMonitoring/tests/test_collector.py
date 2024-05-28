import pytest
import json
import os

from yandextank.common.util import get_test_path
from yandextank.plugins.YCMonitoring.sensor import YCMonitoringSensor


SENSOR = YCMonitoringSensor(
    'counter',
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
    'json_file_name, result_queue',
    [
        (
            'COUNTER.json',
            [
                [
                    {
                        'sensor': 'counter_load-mock-kuber; kube-proxy-bb6kp; kube-system',
                        'timestamp': 1713801680,
                        'value': 581884083,
                    },
                    {
                        'sensor': 'counter_load-mock-kuber; kube-proxy-bb6kp; kube-system',
                        'timestamp': 1713801690,
                        'value': 582131973,
                    },
                    {
                        'sensor': 'counter_load-mock-kuber; kube-proxy-bb6kp; kube-system',
                        'timestamp': 1713801700,
                        'value': 582131973,
                    },
                ]
            ],
        ),
        (
            'DGAUGE.json',
            [
                [
                    {
                        'sensor': 'counter_replica; test_host.net; postgresql_loadtesting',
                        'timestamp': 1714218465,
                        'value': 40.86666666666667,
                    },
                    {
                        'sensor': 'counter_replica; test_host.net; postgresql_loadtesting',
                        'timestamp': 1714218480,
                        'value': 4.220292886953635,
                    },
                ],
                [
                    {
                        'sensor': 'counter_primary; test_host_2.net; postgresql_loadtesting',
                        'timestamp': 1714218465,
                        'value': 61.86666666666667,
                    },
                    {
                        'sensor': 'counter_primary; test_host_2.net; postgresql_loadtesting',
                        'timestamp': 1714218480,
                        'value': 5.166224436732864,
                    },
                ],
            ],
        ),
        (
            'IGAUGE.json',
            [
                [
                    {'sensor': 'counter_test1-instance-group', 'timestamp': 1714227414, 'value': 1},
                    {'sensor': 'counter_test1-instance-group', 'timestamp': 1714227435, 'value': 1},
                ],
                [
                    {'sensor': 'counter_test2-instance-group', 'timestamp': 1714227414, 'value': 1},
                    {'sensor': 'counter_test2-instance-group', 'timestamp': 1714227435, 'value': 1},
                ],
            ],
        ),
        (
            'RATE.json',
            [
                [{'sensor': 'counter_dqtcr5464dbkv1s1rtrt; instance_example; 2', 'timestamp': 1714226079, 'value': 0}],
                [{'sensor': 'counter_dqtcr5464dbkv1s1rtrt; instance_example; 5', 'timestamp': 1714226079, 'value': 0}],
            ],
        ),
    ],
)
def test_queue_after_parsing(json_file_name: str, result_queue: list):
    with open(
        os.path.join(get_test_path(), f'yandextank/plugins/YCMonitoring/tests/{json_file_name}'), 'r'
    ) as json_file:
        data = json.load(json_file)

    current_queue = []
    for idx, sensor_item in enumerate(data['metrics']):
        if not sensor_item:
            continue
        if metrics := SENSOR.parse_metrics(sensor_item, idx):
            current_queue.append(metrics)
    assert current_queue == result_queue
