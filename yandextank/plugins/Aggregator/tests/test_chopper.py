import pytest
import pandas as pd
import numpy as np

from yandextank.plugins.Aggregator.aggregator import phout_columns

from yandextank.plugins.Aggregator.chopper import TimeChopper


@pytest.fixture
def data():
    df = pd.DataFrame(
        np.random.randint(0, 100, (10000, len(phout_columns))),
        columns=phout_columns).set_index('time').sort_index()
    return df


class TestChopper(object):
    def test_chopper_works_for_one_chunk(self, data):
        chopper = TimeChopper([data], 5)
        result = list(chopper)
        assert len(result) == 100
