import socket
import os
import tempfile
import time
import unittest
import base64

from yandextank.plugins.Monitoring.agent.agent import CpuStat, Custom, Disk, NetTcp, NetTxRx


if __name__ == '__main__':
    unittest.main()


class MemTestCase(unittest.TestCase):
    def setUp(self):
        self.foo = CpuStat()

    def test_get(self):
        print self.foo.check()
        self.assertEquals(len(self.foo.columns()), len(self.foo.check()))
        time.sleep(1)
        self.assertNotEquals(['0', '0'], self.foo.check())


class CustomTestCase(unittest.TestCase):
    def setUp(self):
        pass

        #def tearDown(self):

    #    self.foo.dispose()
    #    self.foo = None

    def test_custom_(self):
        custom_config = {'tail': [],
                         'call': ['ZGlmZkV4:aWZjb25maWcgLXMgZXRoMCB8IGF3ayAnJDE9PSJldGgwIiB7cHJpbnQgJDR9Jw==:1']}
        self.foo = Custom(**custom_config)

        #self.assertEqual(x, y, "Msg");
        x = self.foo.check()
        print x
        self.assertEquals(["0"], x)
        time.sleep(1)
        y = self.foo.check()
        print y
        assert x != y
        time.sleep(0.5)
        print self.foo.check()

    def test_custom_nodiff(self):
        tail_fd, tailfile = tempfile.mkstemp()
        tail = ["%s:%s:%s" % (base64.b64encode('lbl'), base64.b64encode(tailfile), 0)]
        call = ["%s:%s:%s" % (base64.b64encode('lbl2'), base64.b64encode("date +%s"), 0)]
        self.foo = Custom(call, tail)

        x = self.foo.check()
        print "second test", x
        self.assertNotEquals(["0.0"], x)
        self.assertEquals('0', x[0])
        time.sleep(1)

        tailval = str(time.time())
        os.write(tail_fd, "%s\n" % tailval)
        y = self.foo.check()
        self.assertNotEquals(x[1], y[1])
        self.assertEquals(tailval, y[0])

        time.sleep(2)
        tailval = str(time.time())
        os.write(tail_fd, "%s\n" % tailval)
        z = self.foo.check()
        self.assertEquals(tailval, z[0])
        self.assertNotEquals(y[1], z[1])

    def test_custom_fail(self):
        tail = ["%s:%s:%s" % (base64.b64encode('lbl'), base64.b64encode("notexistent"), 0)]
        call = ["%s:%s:%s" % (base64.b64encode('lbl2'), base64.b64encode("notexistent"), 0)]
        self.foo = Custom(call, tail)

        x = self.foo.check()
        self.assertEquals("0", x[0])
        self.assertEquals("0", x[1])

    def test_custom_fail2(self):
        custom_config = {'tail': [], 'call': ['TnVtUGhyYXNlcw==:Y2F0IC92YXIvdG1wL3N0YXQx:0']}
        self.foo = Custom(**custom_config)

        self.foo.check()


class DiskTestCase(unittest.TestCase):
    def setUp(self):
        self.foo = Disk()

    def test_get(self):
        print self.foo.check()
        self.assertEquals(2, len(self.foo.check()))
        #travis! self.assertNotEquals(['', ''], self.foo.check())
        fd = tempfile.mkstemp()[0]
        os.write(fd, ' ' * 5000000)
        time.sleep(5)
        res = self.foo.check()
        print res
        # travis! self.assertNotEquals(['', ''], res)

    def test_cols(self):
        res = self.foo.columns()
        self.assertEquals(['Disk_read', 'Disk_write'], res)


class NetTcpTestCase(unittest.TestCase):
    def setUp(self):
        self.foo = NetTcp()

    def test_net_tcp_(self):
        print self.foo.check()
        self.assertEquals(3, len(self.foo.check()))
        # travis! self.assertNotEquals(['0', '0', '0'], self.foo.check())


class NetTxRxTestCase(unittest.TestCase):
    def setUp(self):
        self.foo = NetTxRx()

    def test_net_tx_rx_(self):
        self.assertEquals(['0', '0'], self.foo.check())
        time.sleep(2)
        # travis! self.assertNotEquals(['0', '0'], self.foo.check())
        socket.gethostbyname("google.com")
        socket.create_connection(("google.com", 80), 5000)
        time.sleep(2)
        print self.foo.check()

    def test_net_tx_rx_cols(self):
        res = self.foo.columns()
        self.assertEquals(['Net_tx', 'Net_rx', ], res)

