import subprocess
import time
from unittest import mock

import pytest

from yandextank.common.const import RetCode
from yandextank.plugins.Phantom import Plugin


@pytest.fixture
def plugin():
    p = Plugin(mock.MagicMock(), {}, 'phantom')
    p._phantom = mock.MagicMock()
    p.stall_timeout = 600
    p.start_time = time.time() - 3600
    p.process = subprocess.Popen(['sleep', '600'])
    yield p
    if p.process.poll() is None:
        p.process.kill()


def test_stalled_phantom_stops_the_test(plugin):
    plugin.last_data_time = time.time() - 601

    assert plugin.is_test_finished() == RetCode.ERROR
    assert 'stall_timeout' in plugin.errors[0]

    plugin.end_test(RetCode.ERROR)
    assert plugin.process.poll() is not None


def test_fresh_data_keeps_phantom_running(plugin):
    plugin.last_data_time = time.time() - 601
    plugin.on_aggregated_data({'overall': {'interval_real': {'len': 1}}}, {})

    assert plugin.is_test_finished() == RetCode.CONTINUE
    assert not plugin.errors
