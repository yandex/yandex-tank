import numpy as np
import pandas as pd

from conftest import MAX_TS, random_split
from yandextank.aggregator.chopper import TimeChopper


class TestChopper(object):
    def test_one_chunk(self, data):
        chopper = TimeChopper([data], 5)
        result = list(chopper)
        assert len(result) == MAX_TS
        concatinated = pd.concat(r[1] for r in result)
        assert len(data) == len(concatinated), "We did not lose anything"

    def test_multiple_chunks(self, data):
        chunks = random_split(data)
        chopper = TimeChopper(chunks, 5)
        result = list(chopper)
        assert len(result) == MAX_TS
        concatinated = pd.concat(r[1] for r in result)
        assert len(data) == len(concatinated), "We did not lose anything"

    def test_partially_reversed_data(self, data):
        chunks = list(random_split(data))
        chunks[5], chunks[6] = chunks[6], chunks[5]
        chopper = TimeChopper(chunks, 5)
        result = list(chopper)
        assert len(
            result
        ) == MAX_TS, "DataFrame is splitted into proper number of chunks"
        concatinated = pd.concat(r[1] for r in result)
        assert len(data) == len(concatinated), "We did not lose anything"
        assert np.allclose(
            concatinated.values, data.values), "We did not corrupt the data"
