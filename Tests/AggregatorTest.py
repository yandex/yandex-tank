from Tank.Core import TankCore
from Tank.Plugins.Aggregator import AggregatorPlugin
from Tests.TankTests import TankTestCase
import time
import unittest
from Tank.Plugins.Phantom import PhantomReader


class  AggregatorPluginTestCase(TankTestCase):
    def setUp(self):
        core = TankCore()
        core.load_configs(['config/aggregator.conf'])
        self.foo = AggregatorPlugin(core)

    def tearDown(self):
        del self.foo
        self.foo = None        

    def test_run(self):
        self.foo.configure()
        self.foo.prepare_test()
        self.foo.reader=PhantomReader(self.foo, 'data/phout_example.txt', 'data/phantom_stat.txt')
        self.foo.start_test()
        retry = 0
        while self.foo.is_test_finished() < 0 and retry < 5:
            self.foo.log.debug("Not finished")
            time.sleep(0.01)
            retry = retry + 1
        self.foo.end_test(0)

    def test_run_final_read(self):
        self.foo.configure()
        self.foo.prepare_test()
        self.foo.reader=PhantomReader(self.foo, 'data/phout_example.txt', 'data/phantom_stat.txt')
        self.foo.start_test()
        self.foo.end_test(0)
        
    def test_run_interrupt(self):
        self.foo.configure()
        self.foo.prepare_test()
        self.foo.start_test()
        time.sleep(2)
        self.foo.end_test(0)

if __name__ == '__main__':
    unittest.main()
