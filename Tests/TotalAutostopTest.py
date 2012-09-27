from Tank.Core import TankCore
from Tank.Plugins.Aggregator import AggregatorPlugin, SecondAggregateData
from Tank.Plugins.Autostop import AutostopPlugin
from Tank.Plugins.TotalAutostop import TotalAutostopPlugin
from Tests.TankTests import TankTestCase
import os
import tempfile
import unittest


class TotalAutostopTestCase(TankTestCase):
    def setUp(self):
        self.core = TankCore()
        name = tempfile.mkstemp()[1]
        self.core.config.set_out_file(name)
        self.core.load_configs(['Tests/config/totalautostop.conf'])
        self.core.load_plugins()
#        self.core.plugins_configure()
        self.foo = self.core.get_plugin_of_type(TotalAutostopPlugin)
#        self.foo = TotalAutostopPlugin(self.core)

    def tearDown(self):
        del self.foo
        self.foo = None 

    #def callback(self, data):
        #self.data = SecondAggregateData(data)

    def test_run(self):
        data = list()

        for i in range(0, 20):
            data.append(SecondAggregateData())
            data[i].overall.times_dist = [
                {'count': 10, 'to': 10, 'from': 0},
                {'count': i+1, 'to': 20, 'from': 10}]

        self.foo.core.set_option(TotalAutostopPlugin.SECTION, "autostop", "total_time(10ms,10%,3s)")
        
        self.foo.configure()
        self.foo.prepare_test()
        
        self.foo.start_test()

        Atstp

        print self.core.get_plugin_of_type(AutostopPlugin).custom_criterias
        for x in data:
            self.core.get_plugin_of_type(AutostopPlugin).aggregate_second(x)
            #print x.overall.times_dist[-1]['count']
        if self.foo.is_test_finished() < 0:
            raise RuntimeError()
        self.foo.end_test(0)

    # def test_run_time(self):
    #     data = self.get_test_second()

    #     self.foo.core.set_option(self.foo.SECTION, "autostop", "schi_time (100ms, 90%, 3s)\n")

    #     self.foo.configure()
    #     self.foo.prepare_test()

    #     self.foo.start_test()
    #     for n in range(1, 15):
    #         self.foo.aggregate_second(data)
    #     if self.foo.is_test_finished() < 0:
    #         raise RuntimeError()
    #     self.foo_end_test(0)

    # def test_run_http(self):
    #     data = self.get_test_second()
        
    #     self.foo.core.set_option(self.foo.SECTION, "autostop", "http (200, 10, 5 )\nhttp (3xx, 1.5%, 10m)")
        
    #     self.foo.configure()
    #     self.foo.prepare_test()
        
    #     self.foo.start_test()
    #     for n in range(1, 15):
    #         self.foo.aggregate_second(data)
    #     if self.foo.is_test_finished() < 0:
    #         raise RuntimeError()
    #     self.foo.end_test(0)
        
    # def test_run_net(self):
    #     data = self.get_test_second()
        
    #     self.foo.core.set_option(self.foo.SECTION, "autostop", "net (71, 1, 5)\nnet (xx, 1.5%, 10m )")
        
    #     self.foo.configure()
    #     self.foo.prepare_test()
        
    #     self.foo.start_test()
    #     for n in range(1, 15):
    #         self.foo.aggregate_second(data)
    #     if self.foo.is_test_finished() < 0:
    #         raise RuntimeError()
    #     self.foo.end_test(0)
        
    # def test_run_inst(self):
    #     data = self.get_test_second()
        
    #     self.foo.core.set_option(self.foo.SECTION, "autostop", "instances (5, 5)\ninstances (90%, 10m)")
        
    #     self.foo.configure()
    #     self.foo.prepare_test()
        
    #     self.foo.start_test()
    #     for n in range(1, 15):
    #         self.foo.aggregate_second(data)
    #     if self.foo.is_test_finished() < 0:
    #         raise RuntimeError()
    #     self.foo.end_test(0)

    # def test_run_multiconf(self):
    #     self.foo.core.set_option(self.foo.SECTION, "autostop", "instances (5, 5)\ninstances (90%, 10m) instances (90%, 10m)")
        
    #     self.foo.configure()
    #     self.foo.prepare_test()
    #     self.assertEquals(3, len(self.foo.criterias))
        
if __name__ == '__main__':
    unittest.main()

