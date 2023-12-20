import pandas as pd
import os

from pandas.testing import assert_frame_equal

from yandextank.contrib.netort.netort.data_manager.common.interfaces import TypeQuantiles, TypeHistogram, TypeDistribution
import pytest
PATH = 'netort/data_manager/metrics/tests/'


@pytest.mark.xfail
def test_processor():
    data = pd.read_csv(os.path.join(PATH, 'df1_buffered.csv'))
    aggregated = TypeQuantiles.processor(data, True)
    assert all([col in aggregated.columns for col in TypeQuantiles.columns])


def test_histograms_processor():
    data = pd.read_csv(os.path.join(PATH, 'metric_data_input_event_1.csv'))
    data.loc[:, 'second'] = (data['ts'] / 1000000).astype(int)
    expected = pd.read_csv(os.path.join(PATH, 'metric_data_output_histogram_1.csv'))
    aggregated = TypeHistogram.processor(data)
    assert expected.equals(aggregated)


def test_quantiles_processor():
    data = pd.read_csv(os.path.join(PATH, 'metric_data_input_metric_2.csv'))
    data.loc[:, 'second'] = (data['ts'] / 1000000).astype(int)
    expected = pd.read_csv(os.path.join(PATH, 'metric_data_output_quantile_2.csv'))
    expected = expected.round(2).set_index('second')
    aggregated = TypeQuantiles.processor(data).round(2)
    assert aggregated.equals(expected)


@pytest.mark.skip('broken in arcadia')
def test_distributions_processor():
    data = pd.read_csv(os.path.join(PATH, 'metric_data_input_metric_2.csv'))
    data.loc[:, 'second'] = (data['ts'] / 1000000).astype(int)
    aggregated = TypeDistribution.processor(data).round(2)
    expected = pd.read_csv(os.path.join(PATH, 'metric_data_output_distributions_2.csv')).set_index('second')
    assert_frame_equal(aggregated.sort_index(axis=1), expected.sort_index(axis=1), check_names=False)
