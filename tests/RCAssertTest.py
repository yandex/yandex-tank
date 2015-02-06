from TankTests import TankTestCase
import unittest
from yandextank.plugins.RCAssert import RCAssertPlugin

class RCAssertTestCase(TankTestCase):
    def setUp(self):
        self.core = self.get_core()
        self.foo = RCAssertPlugin(self.core)

    def tearDown(self):
        del self.foo
        self.foo = None

    def test_no_setting(self):
        #self.core.set_option(self.foo.SECTION, 'pass', '')
        self.foo.configure()        
        self.assertEquals(25, self.foo.post_process(25))
        self.assertEquals(0, self.foo.post_process(0))

    def test_set_one(self):
        self.core.set_option(self.foo.SECTION, 'pass', '23')
        self.foo.configure()        
        self.assertEquals(0, self.foo.post_process(23))
        self.assertNotEquals(0, self.foo.post_process(0))

    def test_set_multi(self):
        self.core.set_option(self.foo.SECTION, 'pass', '23 0')
        self.foo.configure()        
        self.assertEquals(0, self.foo.post_process(23))
        self.assertEquals(0, self.foo.post_process(0))
        self.assertNotEquals(0, self.foo.post_process(22))


if __name__ == '__main__':
    unittest.main()

