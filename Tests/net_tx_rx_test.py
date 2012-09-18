from Tank.MonCollector.agent.metric.net_tx_rx import NetTxRx
import time
import unittest

class  Net_tx_rx_TestCase(unittest.TestCase):
    def setUp(self):
        self.foo = NetTxRx()

    def test_net_tx_rx_(self):
        self.assertEquals([0,0], self.foo.check())
        time.sleep(2)
        self.assertNotEquals([0,0], self.foo.check())
        time.sleep(2)
        print self.foo.check()

    def test_net_tx_rx_cols(self):
        res=self.foo.columns()
        self.assertEquals(['Net_tx', 'Net_rx', ], res)

if __name__ == '__main__':
    unittest.main()

