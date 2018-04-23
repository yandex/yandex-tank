from utils import random_split, data
import pandas as pd
import numpy as np


def test_random_split(data):
    dataframes = list(random_split(data))
    assert len(dataframes) > 1
    concatinated = pd.concat(dataframes)
    assert len(concatinated) == len(data), "We did not lose anything"
    assert np.allclose(
        concatinated.values, data.values), "We did not corrupt the data"
