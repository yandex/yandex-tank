from Tank.MonCollector.agent.agent import CpuStat, Custom, Disk, NetTcp, NetTxRx
import os
import tempfile
import time
import unittest


if __name__ == '__main__':
    unittest.main()

class  Mem_TestCase(unittest.TestCase):
    def setUp(self):
        self.foo = CpuStat()

    def test_get(self):
        print self.foo.check()
        self.assertEquals(len(self.foo.columns()), len(self.foo.check()))
        time.sleep(1)
        self.assertNotEquals(['0', '0'], self.foo.check())

class  Custom_TestCase(unittest.TestCase):
    def setUp(self):
        pass
    #def tearDown(self):
    #    self.foo.dispose()
    #    self.foo = None

    def test_custom_(self):
        custom_config = {'tail': [], 'call': ['ZGlmZkV4:aWZjb25maWcgLXMgZXRoMCB8IGF3ayAnJDE9PSJldGgwIiB7cHJpbnQgJDR9Jw==:1']}
        self.foo = Custom(**custom_config)

        #self.assertEqual(x, y, "Msg");
        x = self.foo.check()
        print x
        self.assertEquals(["0"], x)
        time.sleep(1)
        y = self.foo.check()
        print y
        assert x != y;
        time.sleep(0.5)
        print self.foo.check()
        
    def test_custom_nodiff(self):
        custom_config = {'tail': [], 'call': ['ZGlmZkV4:aWZjb25maWcgLXMgZXRoMCB8IGF3ayAnJDE9PSJldGgwIiB7cHJpbnQgJDR9Jw==:0']}
        self.foo = Custom(**custom_config)

        x = self.foo.check()
        print "second test", x
        self.assertNotEquals(["0.0"], x)
        time.sleep(1)
        y = self.foo.check()
        time.sleep(0.5)
        z = self.foo.check()
        print z
        
    def test_custom_fail(self):
        custom_config = {'tail': [], 'call': ['cXVlcnkgY291bnQ=:cXVlcnlfY2xhc3NpZnlfY2xpZW50IGZzdGF0cyB8IGdyZXAgY2xhc3MtY21kIHwgY3V0IC1mIDM=:1']}
        self.foo = Custom(**custom_config)

        x = self.foo.check()
        
    def test_custom_fail2(self):
        custom_config = {'tail': [], 'call': ['TnVtUGhyYXNlcw==:Y2F0IC92YXIvdG1wL3N0YXQx:0']}
        self.foo = Custom(**custom_config)

        x = self.foo.check()


class  Disk_TestCase(unittest.TestCase):
    def setUp(self):
        self.foo = Disk()

    def test_get(self):
        print self.foo.check()
        self.assertEquals(2, len(self.foo.check()))
        self.assertNotEquals(['', ''], self.foo.check())
        fd = tempfile.mkstemp()[0]
        os.write(fd, ' ' * 5000)
        time.sleep(1)
        self.assertNotEquals(['', ''], self.foo.check())

    def test_cols(self):
        res = self.foo.columns()
        self.assertEquals(['Disk_read', 'Disk_write'], res)



class  Net_tcp_TestCase(unittest.TestCase):
    def setUp(self):
        self.foo = NetTcp()

    def test_net_tcp_(self):
        print self.foo.check()
        self.assertEquals(4, len(self.foo.check()))
        self.assertNotEquals(['0','0','0','0'], self.foo.check())


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

