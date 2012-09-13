from Tank.Core import TankCore
from Tank.Plugins.Aggregator import AggregatorPlugin, SecondAggregateData
from Tank.Plugins.Autostop import AutostopPlugin
from Tests.TankTests import TankTestCase
import os
import tempfile
import unittest


class AutostopTestCase(TankTestCase):
    def setUp(self):
        core = TankCore()
        (handler, name) = tempfile.mkstemp()
        core.config.set_out_file(name)
        core.load_configs(['config/autostop.conf'])
        core.load_plugins()
        core.plugins_check_config()
        self.foo = AutostopPlugin(core)

    def tearDown(self):
        del self.foo
        self.foo = None 

    def callback(self, data):
        self.data = SecondAggregateData(data)

    def get_test_second(self):
        fh = open(os.path.realpath('data/preproc_single2.txt'), 'r')
        aggregator = AggregatorPlugin(None)
        aggregator.read_preproc_lines(fh, self.callback)
        return self.data
    
    
    def test_run(self):
        data = self.get_test_second()
        
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
        data = self.get_test_second()
        
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
        data = self.get_test_second()
        
        self.foo.core.set_option(self.foo.SECTION, "autostop", "net (71, 1, 5)\nnet (xx, 1.5%, 10m )")
        
        self.foo.configure()
        self.foo.prepare_test()
        
        self.foo.start_test()
        for n in range(1, 15):
            self.foo.aggregate_second(data)
        if self.foo.is_test_finished() < 0:
            raise RuntimeError()
        self.foo.end_test(0)
        
    def test_run_inst(self):
        data = self.get_test_second()
        
        self.foo.core.set_option(self.foo.SECTION, "autostop", "instances (5, 5)\ninstances (90%, 10m)")
        
        self.foo.configure()
        self.foo.prepare_test()
        
        self.foo.start_test()
        for n in range(1, 15):
            self.foo.aggregate_second(data)
        if self.foo.is_test_finished() < 0:
            raise RuntimeError()
        self.foo.end_test(0)

    def test_run_multiconf(self):
        self.foo.core.set_option(self.foo.SECTION, "autostop", "instances (5, 5)\ninstances (90%, 10m) instances (90%, 10m)")
        
        self.foo.configure()
        self.foo.prepare_test()
        self.assertEquals(3, len(self.foo.criterias))
        
if __name__ == '__main__':
    unittest.main()

