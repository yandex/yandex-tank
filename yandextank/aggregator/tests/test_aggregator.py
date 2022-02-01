import os
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


@pytest.mark.parametrize('phout, expected_rps', [
    ('yandextank/aggregator/tests/phout1', 300)
])
def test_agregator(phout, expected_rps):
    generator = PhantomMock(os.path.join(get_test_path(), phout))
    poller = DataPoller(poll_period=0.1, max_wait=31)
    aggregator = TankAggregator(generator, poller)
    listener = ListenerMock()
    aggregator.add_result_listener(listener)
    aggregator.start_test()
    generator.finished.set()
    while not aggregator.is_aggr_finished():
        aggregator.is_test_finished()
    aggregator.end_test(1)
    assert abs(listener.avg - expected_rps) < 0.1 * expected_rps
