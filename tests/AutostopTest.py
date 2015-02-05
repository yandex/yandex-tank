from yandextank.plugins.Aggregator import SecondAggregateData
from yandextank.plugins.Autostop import AutostopPlugin
from TankTests import TankTestCase
import tempfile
import unittest


class AutostopTestCase(TankTestCase):
    def setUp(self):
        core = self.get_core()
        core.load_configs(['config/autostop.conf'])
        core.load_plugins()
        core.plugins_configure()
        self.foo = AutostopPlugin(core)

    def tearDown(self):
        del self.foo
        self.foo = None 

    def test_run(self):
        data = SecondAggregateData()
        data.overall.avg_response_time = 11
        self.foo.core.set_option(self.foo.SECTION, "autostop", "time(1,10)")
        
        self.foo.configure()
        self.foo.prepare_test()
        
        self.foo.start_test()
        for n in range(1, 15):
            self.foo.aggregate_second(data)
        if self.foo.is_test_finished() < 0:
            raise RuntimeError()
        self.foo.end_test(0)
        
    def test_run_http(self):
        data = SecondAggregateData()
        data.overall.http_codes = {'200':11}
        self.foo.core.set_option(self.foo.SECTION, "autostop", "http (200, 10, 5 )\nhttp (3xx, 1.5%, 10m)")
        
        self.foo.configure()
        self.foo.prepare_test()
        
        self.foo.start_test()
        for n in range(1, 15):
            self.foo.aggregate_second(data)
        if self.foo.is_test_finished() < 0:
            raise RuntimeError()
        self.foo.end_test(0)
        
    def test_run_net(self):
        data = SecondAggregateData()
        data.overall.net_codes = {71:11}
        self.foo.core.set_option(self.foo.SECTION, "autostop", "net (71, 1, 5)\nnet (xx, 1.5%, 10m )")
        
        self.foo.configure()
        self.foo.prepare_test()
        
        self.foo.start_test()
        for n in range(1, 15):
            self.foo.aggregate_second(data)
        if self.foo.is_test_finished() < 0:
            raise RuntimeError()
        self.foo.end_test(0)
        
    def test_run_quan(self):
        data = SecondAggregateData()
        data.overall.quantiles = {99.0:11}
        self.foo.core.set_option(self.foo.SECTION, "autostop", "quantile(99,2,3)")
        
        self.foo.configure()
        self.foo.prepare_test()
        
        self.foo.start_test()
        for n in range(1, 15):
            self.foo.aggregate_second(data)
        if self.foo.is_test_finished() < 0:
            raise RuntimeError()
        self.foo.end_test(0)

    def test_run_false_trigger_bug(self):
        data = SecondAggregateData()
        data.overall.http_codes = {}
        self.foo.core.set_option(self.foo.SECTION, "autostop", "http (5xx, 100%, 1)")
        
        self.foo.configure()
        self.foo.prepare_test()
        
        self.foo.start_test()
        for n in range(1, 15):
            self.foo.aggregate_second(data)
        if self.foo.is_test_finished() >= 0:
            raise RuntimeError()
        self.foo.end_test(0)
        
if __name__ == '__main__':
    unittest.main()

