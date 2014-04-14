import ConfigParser
import unittest

from Tests.Dummy import DummyPlugin

from Tests.TankTests import TankTestCase
import tankcore


class TankCoreTestCase(TankTestCase):
    def setUp(self):
        self.foo = self.get_core()

    def tearDown(self):
        del self.foo
        self.foo = None

    def test_tank_core_fail(self):
        paths = ['config_err/load_err.conf']
        self.foo.load_configs(paths)
        try:
            self.foo.load_plugins()
            self.fail()
        except ImportError:
            pass

    def test_tank_core(self):
        paths = ['config/load.conf']
        self.foo.load_configs(paths)
        self.assertEquals('passed', self.foo.get_option('dotted', 'test'))

        self.foo.load_plugins()
        self.foo.plugins_configure()
        self.foo.plugins_prepare_test()
        self.foo.plugins_start_test()
        self.foo.wait_for_finish()
        self.foo.add_artifact_file(__file__, 1)
        self.foo.plugins_end_test(0)
        self.foo.plugins_post_process(0)

    def test_strstplit(self):
        str1 = '-Jtarget.address=www.yandex.ru -Jtarget.port=26 -J "load_profile=const(1,60s) line(0,1000,10m)"'
        arr1 = tankcore.splitstring(str1)
        self.assertEquals(len(arr1), 5)

    def test_get_multiline_option_filled(self):
        obj = DummyPlugin(self.get_core())
        self.assertEqual(["/dev/null"], obj.get_multiline_option("test", ["/dev/null"]))

    def test_get_multiline_option_filled_empty(self):
        obj = DummyPlugin(self.get_core())
        self.assertEqual((), obj.get_multiline_option("test", ()))

    def test_get_multiline_option_none(self):
        obj = DummyPlugin(self.get_core())
        try:
            obj.get_multiline_option("test")
            self.fail()
        except ConfigParser.NoOptionError:
            pass


if __name__ == '__main__':
    unittest.main()
