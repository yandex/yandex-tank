from netort.data_manager.clients import LunaClient
from netort.data_manager.common.interfaces import TypeEvents
import pandas as pd
import pytest


class TestLunaClient(object):

    def setup_method(self):
        self.luna_client = LunaClient(meta={'api_address': 'localhost'}, job=None)
        self.df1 = pd.read_csv('netort/data_manager/tests/df1MetricData.csv')
        self.df2 = pd.read_csv('netort/data_manager/tests/df2MetricData.csv')
        self.events = TypeEvents()

    @pytest.mark.xfail
    def test_two(self):
        self.luna_client.pending_queue.put([self.events, self.df1])
        assert 5 == 5

    def teardown(self):
        # self.luna_client.register_worker.stop()
        # self.luna_client.register_worker.join()
        # self.luna_client.worker.stop()
        # self.luna_client.worker.join()
        pass
