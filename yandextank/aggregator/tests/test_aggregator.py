from threading import Event

import pytest as pytest

from yandextank.aggregator import TankAggregator
from yandextank.plugins.Phantom import PhantomReader


class PhantomMock(object):
    def __init__(self, phout):
        self.phout_filename = phout
        self.reader = None
        self.finished = Event()

    def get_reader(self):
        if self.reader is None:
            # def reader(phout):
            #     with open(phout) as f:
            #         while True:
            #             line = f.readline()
            #             if line:
            #                 print '.'
            #                 yield string_to_df(line)
            #             else:
            #                 self.finished.set()
            #                 break
            self.reader = PhantomReader(self.phout_filename, ready_file=True)
        return self.reader

    def get_stats_reader(self):
        return (i for i in [])

    def end_test(self, retcode):
        return retcode


class ListenerMock(object):
    def __init__(self, expected):
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
    generator = PhantomMock(phout)
    aggregator = TankAggregator(generator)
    listener = ListenerMock(expected_rps)
    aggregator.add_result_listener(listener)
    aggregator.start_test(poll_period=0)
    while not generator.reader.closed:
        aggregator.is_test_finished()
    aggregator.end_test(1)
    assert abs(listener.avg - expected_rps) < 0.1 * expected_rps
