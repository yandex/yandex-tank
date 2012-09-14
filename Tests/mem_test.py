import unittest
from MonCollector.agent.metric.mem import Mem


class  Mem_TestCase(unittest.TestCase):
    def setUp(self):
        self.foo = Mem()

    def test_get(self):
        print self.foo.check()
        self.assertNotEquals([0,0], self.foo.check())

    def test_cols(self):
        res=self.foo.columns()
        self.assertEquals(['Memory_total',  'Memory_used', 'Memory_free', 'Memory_shared', 'Memory_buff', 'Memory_cached'], res)

if __name__ == '__main__':
    unittest.main()

