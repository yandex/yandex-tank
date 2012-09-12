from Tank.Core import TankCore
from Tank.Plugins.Aggregator import AggregatorPlugin
from Tests.TankTests import TankTestCase
import os
import tempfile
import time
import unittest


class  AggregatorPluginTestCase(TankTestCase):
    def setUp(self):
        core = TankCore()
        core.load_configs(['config/aggregator.conf'])
        self.foo = AggregatorPlugin(core)

    def tearDown(self):
        del self.foo
        self.foo = None
        os.remove("lp.conf")
        os.remove("lunapark.log")
        

    def test_run(self):
        self.foo.configure()
        (drop, self.foo.preproc_out_filename) = tempfile.mkstemp()
        self.foo.prepare_test()
        self.foo.start_test()
        retry = 0
        while self.foo.is_test_finished() < 0 and retry < 5:
            self.foo.log.debug("Not finished")
            time.sleep(1)
            retry = retry + 1
        self.foo.end_test(0)
        
    def test_run_interrupt(self):
        self.foo.configure()
        (drop, self.foo.preproc_out_filename) = tempfile.mkstemp()
        self.foo.prepare_test()
        self.foo.start_test()
        time.sleep(2)
        self.foo.end_test(0)

if __name__ == '__main__':
    unittest.main()
