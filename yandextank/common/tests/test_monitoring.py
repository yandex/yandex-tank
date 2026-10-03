import logging
import threading
import time
from queue import Queue

import pytest
from yandextank.common.monitoring import DefaultCollector, MonitoringPanel, monitoring_data


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


def test_collector_stop_does_not_wait_for_hung_sensor():
    started, release = threading.Event(), threading.Event()

    class HungSensor:
        def fetch_metrics(self):
            started.set()
            release.wait()

    collector = DefaultCollector(logger=logging.getLogger(__name__), timeout=0.2, poll_interval=0.01)
    collector.add_sensor(HungSensor())
    collector.add_panel(MonitoringPanel('panel', 0.2, Queue()))
    collector.start()
    assert started.wait(5)

    unhang = threading.Timer(10, release.set)  # on regression stop() returns after ~10 s instead of hanging
    unhang.start()
    begin = time.monotonic()
    try:
        collector.stop()
        elapsed = time.monotonic() - begin
        assert collector.sensors[0].is_alive()
    finally:
        unhang.cancel()
        release.set()
    # 1.01 s grace sleep + 0.2 s bounded wait for sensors and panels
    assert elapsed < 3


def test_collector_stop_fetches_after_grace_sleep():
    # a lagging source has the tail of the test only after the grace sleep of stop()
    queue = Queue()
    collector = DefaultCollector(logger=logging.getLogger(__name__), timeout=0.2, poll_interval=0.01)

    class LaggingSensor:
        def fetch_metrics(self):
            if collector.stop_event.is_set():
                queue.put({'sensor': 'cpu', 'timestamp': 42, 'value': 1})

    collector.add_sensor(LaggingSensor())
    collector.add_panel(MonitoringPanel('panel', 0.2, queue))
    collector.start()
    collector.stop()
    assert [chunk['timestamp'] for chunk in collector.poll()] == [42]
