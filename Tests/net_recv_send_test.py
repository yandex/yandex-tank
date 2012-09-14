from MonCollector.agent.metric.net import Net
import logging
import time
import unittest

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s %(message)s")
logging.info("Begin")

class  Net_tcp_TestCase(unittest.TestCase):
    def setUp(self):
        self.foo = Net()

    def test_net_tcp_(self):
        print self.foo.check()
        self.assertEquals(2, len(self.foo.check()))
        self.assertNotEquals(['', ''], self.foo.check())
        time.sleep(2)
        self.assertNotEquals(['0', '0'], self.foo.check())

if __name__ == '__main__':
    unittest.main()

    

