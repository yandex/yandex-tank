import unittest

from Tank.Plugins.ResourceCheck import ResourceCheckPlugin

from Tests.TankTests import TankTestCase


class RCheckTestCase(TankTestCase):
    def setUp(self):
        self.core = self.get_core()
        self.foo = ResourceCheckPlugin(self.core)

    def tearDown(self):
        del self.foo
        self.foo = None

    def test_no_setting(self):
        #self.core.set_option(self.foo.SECTION, 'pass', '')
        self.foo.configure()
        self.foo.prepare_test()


if __name__ == '__main__':
    unittest.main()

