import json
import os

import numpy as np
import pytest

from queue import Queue

from yandextank.common.util import get_test_path
from conftest import random_split

from yandextank.aggregator import TankAggregator
from yandextank.aggregator.aggregator import Aggregator, DataPoller
from yandextank.aggregator.chopper import TimeChopper
from yandextank.plugins.Phantom.reader import string_to_df
from load.contrib.netort.data_processing import Drain

AGGR_CONFIG = TankAggregator.load_config()

# Порядку чанков хватает 300 секунд data.csv: агрегация всей 1000 шла 10-16 с на тест, и два таких теста
# в одном чанке SMALL не укладывались в 60 с на медленном хосте CI (LOAD-3845).
PIPELINE_TS = 300


def _swap_middle_chunks(chunks):
    assert len(chunks) >= 2
    middle = len(chunks) // 2
    chunks[middle - 1], chunks[middle] = chunks[middle], chunks[middle - 1]


class TestPipeline(object):
    def test_partially_reversed_data(self, data):
        results_queue = Queue()
        chunks = list(random_split(data.loc[: PIPELINE_TS - 1]))
        _swap_middle_chunks(chunks)

        # poll_period 0.01: данные уже в памяти, DataPoller нечего ждать между чанками (LOAD-3675).
        pipeline = Aggregator(TimeChopper([DataPoller(poll_period=0.01, max_wait=31).poll(chunks)]), AGGR_CONFIG, False)
        drain = Drain(pipeline, results_queue)
        drain.run()
        assert results_queue.qsize() == PIPELINE_TS

    def test_slow_producer(self, data):
        results_queue = Queue()
        chunks = list(random_split(data.loc[: PIPELINE_TS - 1]))
        _swap_middle_chunks(chunks)

        def producer():
            for chunk in chunks:
                if np.random.random() > 0.5:
                    yield None
                yield chunk

        # poll_period 0.01: данные уже в памяти, DataPoller нечего ждать между чанками (LOAD-3675).
        pipeline = Aggregator(
            TimeChopper([DataPoller(poll_period=0.01, max_wait=31).poll(producer())]), AGGR_CONFIG, False
        )
        drain = Drain(pipeline, results_queue)
        drain.run()
        assert results_queue.qsize() == PIPELINE_TS

    @pytest.mark.parametrize(
        'phout, expected_results',
        [('yandextank/aggregator/tests/phout2927', 'yandextank/aggregator/tests/phout2927res.jsonl')],
    )
    def test_invalid_ammo(self, phout, expected_results):
        with open(os.path.join(get_test_path(), phout)) as fp:
            reader = [string_to_df(line) for line in fp.readlines()]
        pipeline = Aggregator(TimeChopper([DataPoller(poll_period=0.01, max_wait=31).poll(reader)]), AGGR_CONFIG, True)
        with open(os.path.join(get_test_path(), expected_results)) as fp:
            expected_results_parsed = json.load(fp)
        for item, expected_result in zip(pipeline, expected_results_parsed):
            for key, expected_value in expected_result.items():
                assert item[key] == expected_value
