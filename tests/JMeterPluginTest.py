import logging
import time
import unittest

from yandextank.plugins.JMeter import JMeterPlugin, JMeterReader
from TankTests import TankTestCase
from yandextank.plugins.Aggregator import AggregatorPlugin


class JMeterPluginTestCase(TankTestCase):
    def setUp(self):
        self.core = self.get_core()
        self.core.load_configs(['config/jmeter.conf'])
        self.foo = JMeterPlugin(self.core)

    def tearDown(self):
        del self.foo
        self.foo = None

    def test_run(self):
        self.foo.configure()
        self.foo.prepare_test()
        self.foo.start_test()
        while self.foo.is_test_finished() < 0:
            self.foo.log.debug("Not finished")
            time.sleep(1)
        self.foo.end_test(0)
        results = open(self.foo.jtl_file, 'r').read()
        logging.debug("Results: %s", results)
        self.assertNotEquals('', results.strip(), open(self.foo.jmeter_log, 'r').read())

    def test_run_interrupt(self):
        self.foo.configure()
        self.foo.prepare_test()
        self.foo.start_test()
        time.sleep(2)
        self.foo.end_test(0)

    def test_reader(self):
        aggregator = AggregatorPlugin(self.core)
        self.foo.jtl_file = 'data/jmeter_mtuV0x.jtl'
        reader = JMeterReader(aggregator, self.foo)
        reader.check_open_files()
        self.assertNotEquals(None, reader.get_next_sample(False))
        self.assertNotEquals(None, reader.get_next_sample(True))
        cnt = 2
        while reader.get_next_sample(True):
            cnt += 1
        self.assertEquals(55, cnt)

    def test_reader_errors(self):
        aggregator = AggregatorPlugin(self.core)
        self.foo.jtl_file = 'data/jmeter_HifF2z.jtl'
        reader = JMeterReader(aggregator, self.foo)
        reader.check_open_files()
        self.assertNotEquals(None, reader.get_next_sample(False))
        self.assertNotEquals(None, reader.get_next_sample(True))
        cnt = 2
        while reader.get_next_sample(True):
            cnt += 1
        self.assertEquals(5, cnt)


if __name__ == '__main__':
    unittest.main()
