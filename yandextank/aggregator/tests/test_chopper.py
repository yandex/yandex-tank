import pandas as pd

from conftest import MAX_TS, random_split
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
