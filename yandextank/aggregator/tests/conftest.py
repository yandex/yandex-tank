import numpy as np
import pandas as pd
import pytest

from yandextank.aggregator.aggregator import phout_columns

np.random.seed(42)
MAX_TS = 1000


def random_split(df):
    i = 0
    while True:
        step = np.random.randint(500, 1200)
        if i + step < len(df):
            yield df.ix[i:i + step - 1]
            i += step
        else:
            yield df.ix[i:]
            break


@pytest.fixture
def data():
    df = pd.DataFrame(
        np.random.randint(0, MAX_TS, (10000, len(phout_columns))),
        columns=phout_columns).set_index('time').sort_index()
    df['tag'] = np.random.choice(list(range(3)), len(df))
    return df
