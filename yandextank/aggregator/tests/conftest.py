import os
import numpy as np
import pandas as pd
import pytest

from yandextank.common.util import get_test_path

MAX_TS = 1000


def random_split(df):
    i = 0
    while i < max(df.index):
        step = np.random.randint(100, 200)
        if i + step < max(df.index):
            yield df.loc[i:i + step - 1]
        else:
            yield df.loc[i:]
        i += step


@pytest.fixture
def data():
    df = pd.read_csv(os.path.join(get_test_path(), 'yandextank/aggregator/tests/data.csv'), delimiter=',', index_col=0)
    return df
