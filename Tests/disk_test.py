from Tank.MonCollector.agent.metric.disk import Disk
import time
import unittest


class  Mem_TestCase(unittest.TestCase):
    def setUp(self):
        self.foo = Disk()

    def test_get(self):
        print self.foo.check()
        self.assertEquals(2, len(self.foo.check()))
        self.assertNotEquals(['', ''], self.foo.check())
        time.sleep(5)
        self.assertNotEquals(['0', '0'], self.foo.check())

    def test_cols(self):
        res = self.foo.columns()
        self.assertEquals(['Disk_read', 'Disk_write'], res)

if __name__ == '__main__':
    unittest.main()

