import time

import pandas as pd

from conftest import MAX_TS, random_split
from yandextank.aggregator import aggregator
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


def test_poller_sleeps_only_without_data(monkeypatch):
    # Сон после каждого чанка давал не больше 1/poll_period чанков в секунду на ступень (LOAD-3937).
    slept = []
    monkeypatch.setattr(aggregator.time, 'sleep', slept.append)
    chunks = [[i] for i in range(100)]
    poller = DataPoller(poll_period=0.5, max_wait=1)
    # Пустой список — секунда без новой статистики у Bfg и Pandora: после него поллер спит.
    assert list(poller.poll(iter(chunks + [[]] + [None] * 5))) == chunks + [[]]
    # Спит пустую итерацию и тишину после данных, тишину — не дольше max_wait.
    assert slept == [0.5, 0.5, 0.5]
