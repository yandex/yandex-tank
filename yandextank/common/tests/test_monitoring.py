import pytest
from yandextank.common.monitoring import monitoring_data


@pytest.mark.parametrize(
    'metrics, result',
    [
        (
            {1: {'sens1': 1, 'sens2': 2}},
            {'timestamp': 1, 'data': {'test': {'comment': '', 'metrics': {'custom:sens1': 1, 'custom:sens2': 2}}}},
        )
    ],
)
def test_monitoring_data(metrics, result):
    assert monitoring_data('test', metrics, '') == result
