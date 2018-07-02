import json
import numpy as np
import pytest

from queue import Queue
from conftest import MAX_TS, random_split

from yandextank.aggregator import TankAggregator
from yandextank.aggregator.aggregator import Aggregator, DataPoller
from yandextank.aggregator.chopper import TimeChopper
from yandextank.plugins.Phantom.reader import string_to_df

from netort.data_processing import Drain


AGGR_CONFIG = TankAggregator.load_config()


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

    @pytest.mark.parametrize('phout, expected_results', [
        ('yandextank/aggregator/tests/phout2927', 'yandextank/aggregator/tests/phout2927res.jsonl')
    ])
    def test_invalid_ammo(self, phout, expected_results):
        with open(phout) as fp:
            reader = [string_to_df(line) for line in fp.readlines()]
        pipeline = Aggregator(
            TimeChopper(
                DataPoller(source=reader, poll_period=0),
                cache_size=3),
            AGGR_CONFIG,
            True)
        with open(expected_results) as fp:
            expected_results_parsed = json.load(fp)
        for item, expected_result in zip(pipeline, expected_results_parsed):
            for key, expected_value in expected_result.items():
                assert item[key] == expected_value
