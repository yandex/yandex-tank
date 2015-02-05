from TankTests import TankTestCase
import unittest
from yandextank.plugins.ApacheBenchmark import ABReader, ApacheBenchmarkPlugin
from yandextank.plugins.Aggregator import AggregatorPlugin

class ABTestCase(TankTestCase):
    def setUp(self):
        self.core = self.get_core()
        self.foo = ApacheBenchmarkPlugin(self.core)

    def tearDown(self):
        del self.foo
        self.foo = None

    def test_run(self):
        aggregator = AggregatorPlugin(self.core)
        self.foo.out_file = 'data/ab_results.txt'
        reader = ABReader(aggregator, self.foo)
        reader.check_open_files()
        self.assertNotEquals(None, reader.get_next_sample(False))
        self.assertNotEquals(None, reader.get_next_sample(True))
        cnt = 2
        while reader.get_next_sample(True):
            cnt += 1
        self.assertEquals(25, cnt)
    
if __name__ == '__main__':
    unittest.main()

