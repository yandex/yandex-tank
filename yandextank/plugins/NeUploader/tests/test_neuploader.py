import pandas as pd
import pytest
import json

from numpy.testing import assert_array_equal

from yandextank.plugins.NeUploader.plugin import Plugin


class TestMonitoringData(object):

    @pytest.mark.parametrize('mon_data, length', [
        ('yandextank/plugins/NeUploader/tests/monitoring_data/monitoring1.json', 54),
    ])
    def test_df_num_and_cols(self, mon_data, length):
        with open(mon_data) as f:
            jsondata = json.load(f)
            dfs = Plugin.monitoring_data_to_dfs(jsondata)
        assert len(dfs) == length
        assert all([list(df.columns) == ['ts', 'value'] for df in dfs.values()])

    @pytest.mark.parametrize('mon_data, names', [
        ('yandextank/plugins/NeUploader/tests/monitoring_data/monitoring1.json',
         ()),
    ])
    def test_metrics_names(self, mon_data, names):
        with open(mon_data) as f:
            jsondata = json.load(f)
            dfs = Plugin.monitoring_data_to_dfs(jsondata)
        assert set(dfs.keys()) == {'{}:{}'.format(panelk, name) for i in jsondata for panelk, panelv in i['data'].items() for name in panelv['metrics'].keys()}


DF = pd.DataFrame({'ts': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
                   'value': [43, 75, 12, 65, 24, 65, 41, 87, 15, 62],
                   'tag': ['foo', 'bar', 'foo', '', '', 'null', '', 'not_null', '', 'foo']})


@pytest.mark.parametrize('df, case, expected', [
    (DF, '__overall__', DF[['ts', 'value']]),
    (DF, 'foo', pd.DataFrame({'ts': [0, 2, 9],
                              'value': [43, 12, 62]})),
    (DF, 'null', pd.DataFrame({'ts': [5],
                               'value': [65]}))
])
def test_filter_df_by_case(df, case, expected):
    assert_array_equal(Plugin.filter_df_by_case(df, case), expected, )
