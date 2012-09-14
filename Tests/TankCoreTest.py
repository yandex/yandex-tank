from Tank.Core import TankCore
from Tests.TankTests import TankTestCase
import os
import tempfile
import unittest

class  TankCoreTestCase(TankTestCase):
    def setUp(self):
        self.foo = TankCore()
        (handler, name) = tempfile.mkstemp()
        self.foo.config.set_out_file(name)

    def tearDown(self):
        del self.foo
        self.foo = None

    def test_tankCoreFail(self):
        paths = ['config_err/load_err.conf']
        self.foo.load_configs(paths)
        try:
            self.foo.load_plugins()
            self.fail()
        except ImportError:
            pass

    def test_tankCore(self):
        paths = ['config/load.conf']
        self.foo.load_configs(paths)
        self.foo.load_plugins()
        self.foo.plugins_configure()
        self.foo.plugins_prepare_test()
        self.foo.plugins_start_test()
        self.foo.wait_for_finish()
        self.foo.add_artifact_file(__file__, 1)
        self.foo.plugins_end_test(0)

    def test_find_plugin(self):
        self.foo.plugins = {'test.pyc': TankCore()}
        self.foo.get_plugin_by_key('test.py')
        

if __name__ == '__main__':
    unittest.main()

