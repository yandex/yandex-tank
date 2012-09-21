from Tank.Core import TankCore
from Tank.Plugins.Aggregator import AggregatorPlugin, AbstractReader
from Tests.TankTests import TankTestCase
import time
import unittest


class  AggregatorPluginTestCase(TankTestCase):
    def setUp(self):
        core = self.get_core()
        core.load_configs(['config/aggregator.conf'])
        self.foo = AggregatorPlugin(core)

    def tearDown(self):
        del self.foo
        self.foo = None        

    def test_run(self):
        self.foo.configure()
        self.foo.prepare_test()
        self.foo.reader=FakeReader(self.foo)
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
        self.foo.reader=FakeReader(self.foo)
        self.foo.start_test()
        self.foo.end_test(0)
        
    def test_run_interrupt(self):
        self.foo.configure()
        self.foo.prepare_test()
        self.foo.start_test()
        time.sleep(2)
        self.foo.end_test(0)

class FakeReader(AbstractReader):
    pass


if __name__ == '__main__':
    unittest.main()
