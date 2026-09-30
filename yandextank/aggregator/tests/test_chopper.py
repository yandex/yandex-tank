import time

import pandas as pd

from conftest import MAX_TS, random_split
from yandextank.aggregator.aggregator import DataPoller
from yandextank.aggregator.chopper import TimeChopper


class TestChopper(object):
    def test_one_chunk(self, data):
        chopper = TimeChopper([iter([data])])
        result = list(chopper)
        assert len(result) == MAX_TS
        concatinated = pd.concat(r[1] for r in result)
        assert len(data) == len(concatinated), "We did not lose anything"

    def test_multiple_chunks(self, data):
        chunks = random_split(data)
        chopper = TimeChopper([iter(chunks)])
        result = list(chopper)
        assert len(result) == MAX_TS
        concatinated = pd.concat(r[1] for r in result)
        assert len(data) == len(concatinated), "We did not lose anything"


def test_pool_silent_longer_than_max_wait():
    # Пул pandora с ops: 0 в начале дольше max_wait: его данные не теряются и не держат другой пул.
    now = int(time.time())
    events = []

    def active():
        yield pd.DataFrame({'x': [1, 1]}, index=[now - 100, now - 99])

    def late():
        for _ in range(20):
            yield None
        events.append('late')
        yield pd.DataFrame({'x': [1, 1, 1]}, index=[now, now, now])

    poller = DataPoller(poll_period=0.001, max_wait=0.005)
    rows = 0
    for ts, data, _ in TimeChopper([poller.poll(active()), poller.poll(late())]):
        events.append(ts)
        rows += len(data)
    assert rows == 5
    assert events.index(now - 100) < events.index('late')
