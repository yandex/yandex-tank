import os
import time
from datetime import datetime
from threading import Event

import pytest as pytest

from yandextank.common.util import get_test_path
from yandextank.aggregator import TankAggregator
from yandextank.aggregator.aggregator import DataPoller
from yandextank.common.util import FileMultiReader
from yandextank.plugins.Phantom.reader import PhantomReader


class PhantomMock(object):
    def __init__(self, phout):
        self.phout_filename = phout
        self.reader = None
        self.finished = Event()

    def get_reader(self):
        if self.reader is None:
            self.reader = PhantomReader(FileMultiReader(self.phout_filename, self.finished).get_file())
        return self.reader

    def get_stats_reader(self):
        return (i for i in [])

    def end_test(self, retcode):
        return retcode


class ListenerMock(object):
    def __init__(self):
        self.collected_data = []
        self.cnt = 0
        self.avg = 0

    def on_aggregated_data(self, data, stats):
        rps = data['counted_rps']
        self.cnt += 1
        self.avg = (self.avg * (self.cnt - 1) + rps) / self.cnt


@pytest.mark.parametrize('phout, expected_rps', [('yandextank/aggregator/tests/phout1', 300)])
def test_agregator(phout, expected_rps):
    generator = PhantomMock(os.path.join(get_test_path(), phout))
    poller = DataPoller(poll_period=0.01, max_wait=31)
    aggregator = TankAggregator(generator, poller)
    listener = ListenerMock()
    aggregator.add_result_listener(listener)
    aggregator.start_test()
    generator.finished.set()
    while not aggregator.is_aggr_finished():
        aggregator.is_test_finished()
        # Пустой цикл отбирал GIL у потока агрегации: тест шёл 14-35 с вместо 2.5 (LOAD-3845).
        time.sleep(0.1)
    aggregator.end_test(1)
    assert abs(listener.avg - expected_rps) < 0.1 * expected_rps


@pytest.mark.parametrize('phout', ['yandextank/aggregator/tests/phout1'])
def test_aggregator_max_timeout(phout):
    generator = PhantomMock(os.path.join(get_test_path(), phout))
    poller = DataPoller(poll_period=0.1, max_wait=31)
    aggregator = TankAggregator(generator, poller, termination_timeout=0.2)
    listener = ListenerMock()
    aggregator.add_result_listener(listener)
    aggregator.start_test()
    termination_start = datetime.now()
    aggregator.end_test(1)
    termination_lag = (datetime.now() - termination_start).total_seconds()
    assert termination_lag < 1
    assert termination_lag > 0.2
    generator.finished.set()


class BrokenReaderMock(object):
    """Ридер данных падает, как JMeter на тексте в числовой колонке (LOAD-3946), а статистика ждёт данных."""

    def __init__(self):
        self.stats_closed = False

    def _reader(self):
        raise ValueError("invalid literal for int() with base 10: 'YA04_wait_for_acquire'")
        yield

    def _stats_reader(self):
        while not self.stats_closed:
            yield None

    def get_reader(self):
        return self._reader()

    def get_stats_reader(self):
        return self

    def __iter__(self):
        return self._stats_reader()

    def close(self):
        self.stats_closed = True

    def end_test(self, retcode):
        return retcode


def test_source_error_finishes_test():
    # max_wait 31 с: раньше стрельба стояла, пока поллер статистики не дождётся тишины (LOAD-3947).
    generator = BrokenReaderMock()
    aggregator = TankAggregator(generator, DataPoller(poll_period=0.01, max_wait=31))
    aggregator.start_test()
    try:
        deadline = time.monotonic() + 5
        retcode = aggregator.is_test_finished()
        while retcode < 0 and time.monotonic() < deadline:
            time.sleep(0.05)
            retcode = aggregator.is_test_finished()
        assert retcode == 1
        assert len(aggregator.errors) == 1
        assert aggregator.errors[0].startswith('Data source failed: ValueError(')
        assert 'YA04_wait_for_acquire' in aggregator.errors[0]
    finally:
        retcode = aggregator.end_test(0)
    # Ошибка источника не даёт кончить стрельбу успехом и не дублируется в итоге.
    assert retcode == 1
    assert len(aggregator.errors) == 1
