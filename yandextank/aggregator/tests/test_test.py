from conftest import random_split
import pandas as pd
import numpy as np


def test_random_split(data):
    dataframes = list(random_split(data))
    assert len(dataframes) > 1
    concatenated = pd.concat(dataframes)
    assert len(concatenated) == len(data), "We did not lose anything"
    assert np.allclose(
        concatenated.values, data.values), "We did not corrupt the data"
