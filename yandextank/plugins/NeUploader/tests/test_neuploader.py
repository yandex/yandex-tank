import pytest
import json
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
