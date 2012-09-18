from Tank.MonCollector.agent.metric.net_tcp import NetTcp
import unittest

class  Net_tcp_TestCase(unittest.TestCase):
    def setUp(self):
        self.foo = NetTcp()

    def test_net_tcp_(self):
        print self.foo.check()
        self.assertEquals(4, len(self.foo.check()))
        self.assertNotEquals(['0','0','0','0'], self.foo.check())

if __name__ == '__main__':
    unittest.main()

