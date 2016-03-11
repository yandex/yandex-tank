import pandas as pd
import numpy as np
import json
from pkg_resources import resource_string
from Queue import Queue, Empty

from yandextank.plugins.Aggregator.chopper import TimeChopper
from yandextank.plugins.Aggregator.aggregator import Aggregator
from yandextank.plugins.Aggregator.plugin import DataPoller
from yandextank.core.util import Drain

from conftest import MAX_TS, random_split

AGGR_CONFIG = json.loads(resource_string("yandextank.plugins.Aggregator",
                                         'config/phout.json'))


class TestPipeline(object):
    def test_partially_reversed_data(self, data):
        results_queue = Queue()
        results = []
        chunks = list(random_split(data))
        chunks[5], chunks[6] = chunks[6], chunks[5]

        pipeline = Aggregator(
            TimeChopper(
                DataPoller(source=chunks,
                           poll_period=0.1),
                cache_size=3),
            AGGR_CONFIG,
            False)
        drain = Drain(pipeline, results_queue)
        drain.run()
        assert results_queue.qsize() == MAX_TS

    def test_slow_producer(self, data):
        results_queue = Queue()
        results = []
        chunks = list(random_split(data))
        chunks[5], chunks[6] = chunks[6], chunks[5]

        def producer():
            for chunk in chunks:
                if np.random.random() > 0.5:
                    yield None
                yield chunk

        pipeline = Aggregator(
            TimeChopper(
                DataPoller(source=producer(),
                           poll_period=0.1),
                cache_size=3),
            AGGR_CONFIG,
            False)
        drain = Drain(pipeline, results_queue)
        drain.run()
        assert results_queue.qsize() == MAX_TS
