from Tank.MonCollector.agent.metric.cpu_stat import CpuStat
import time
import unittest


class  Mem_TestCase(unittest.TestCase):
    def setUp(self):
        self.foo = CpuStat()

    def test_get(self):
        print self.foo.check()
        self.assertEquals(len(self.foo.columns()), len(self.foo.check()))
        time.sleep(1)
        self.assertNotEquals(['0', '0'], self.foo.check())

if __name__ == '__main__':
    unittest.main()

