import time
import unittest

from yandextank.plugins.Aggregator import AggregatorPlugin, AbstractReader, \
    SecondAggregateDataTotalItem
from TankTests import TankTestCase


class AggregatorPluginTestCase(TankTestCase):
    def setUp(self):
        core = self.get_core()
        core.load_configs(['config/aggregator.conf'])
        self.foo = AggregatorPlugin(core)

    def tearDown(self):
        del self.foo
        self.foo = None

    def test_run(self):
        self.foo.configure()
        self.assertEquals(11000, self.foo.get_timeout())
        self.foo.prepare_test()
        self.foo.reader = FakeReader(self.foo)
        self.foo.start_test()
        retry = 0
        while self.foo.is_test_finished() < 0 and retry < 5:
            self.foo.log.debug("Not finished")
            time.sleep(0.01)
            retry += 1
        self.foo.end_test(0)

    def test_run_final_read(self):
        self.foo.configure()
        self.foo.prepare_test()
        self.foo.reader = FakeReader(self.foo)
        self.foo.start_test()
        self.foo.end_test(0)

    def test_run_interrupt(self):
        self.foo.configure()
        self.foo.prepare_test()
        self.foo.start_test()
        time.sleep(2)
        self.foo.end_test(0)

    def test_total_quantiles(self):
        self.foo = SecondAggregateDataTotalItem()
        self.foo.total_count = 1000
        self.foo.times_dist = {2: {'count': 14, 'to': 3, 'from': 2}, 3: {'count': 815, 'to': 4, 'from': 3},
                               4: {'count': 55, 'to': 5, 'from': 4}, 5: {'count': 29, 'to': 6, 'from': 5},
                               6: {'count': 26, 'to': 7, 'from': 6}, 7: {'count': 27, 'to': 8, 'from': 7},
                               8: {'count': 14, 'to': 9, 'from': 8}, 9: {'count': 8, 'to': 10, 'from': 9},
                               10: {'count': 12, 'to': 20, 'from': 10}}
        res = self.foo.calculate_total_quantiles()
        exp = {98.0: 9, 99.0: 20, 100.0: 20, 75.0: 4, 85.0: 5, 80.0: 4, 50.0: 4, 25.0: 4, 90.0: 6, 95.0: 8}
        self.assertDictEqual(exp, res)


class FakeReader(AbstractReader):
    pass


if __name__ == '__main__':
    unittest.main()
