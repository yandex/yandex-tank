import os
import numpy as np
import pandas as pd
import pytest

from yandextank.common.util import get_test_path

MAX_TS = 1000


def random_split(df):
    i = 0
    while True:
        step = np.random.randint(500, 1200)
        if i + step < len(df):
            yield df.loc[i:i + step - 1]
            i += step
        else:
            yield df.loc[i:]
            break


@pytest.fixture
def data():
    df = pd.read_csv(os.path.join(get_test_path(), 'yandextank/aggregator/tests/data.csv'), delimiter=',', index_col=0)
    return df
