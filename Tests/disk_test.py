from Tank.MonCollector.agent.metric.disk import Disk
import time
import unittest
import tempfile
import os


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
        self.assertNotEquals(['0', '0'], self.foo.check())

    def test_cols(self):
        res = self.foo.columns()
        self.assertEquals(['Disk_read', 'Disk_write'], res)

if __name__ == '__main__':
    unittest.main()

