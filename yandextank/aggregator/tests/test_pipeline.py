import json

import numpy as np
from pkg_resources import resource_filename
from queue import Queue
from yandextank.aggregator.aggregator import Aggregator, DataPoller
from yandextank.aggregator.chopper import TimeChopper

from conftest import MAX_TS, random_split
from yandextank.common.util import Drain

with open(resource_filename("yandextank.aggregator", 'config/phout.json')) as f:
    AGGR_CONFIG = json.load(f)


class TestPipeline(object):
    def test_partially_reversed_data(self, data):
        results_queue = Queue()
        chunks = list(random_split(data))
        chunks[5], chunks[6] = chunks[6], chunks[5]

        pipeline = Aggregator(
            TimeChopper(
                DataPoller(
                    source=chunks, poll_period=0.1), cache_size=3),
            AGGR_CONFIG,
            False)
        drain = Drain(pipeline, results_queue)
        drain.run()
        assert results_queue.qsize() == MAX_TS

    def test_slow_producer(self, data):
        results_queue = Queue()
        chunks = list(random_split(data))
        chunks[5], chunks[6] = chunks[6], chunks[5]

        def producer():
            for chunk in chunks:
                if np.random.random() > 0.5:
                    yield None
                yield chunk

        pipeline = Aggregator(
            TimeChopper(
                DataPoller(
                    source=producer(), poll_period=0.1), cache_size=3),
            AGGR_CONFIG,
            False)
        drain = Drain(pipeline, results_queue)
        drain.run()
        assert results_queue.qsize() == MAX_TS
