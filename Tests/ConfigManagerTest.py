from Tank.ConsoleWorker import ConsoleTank
from Tank.Core import ConfigManager
from Tests.TankTests import TankTestCase, FakeOptions
import os
import tempfile
import unittest

class  ConfigManagerTestCase(TankTestCase):
    def setUp(self):
        tank = ConsoleTank(FakeOptions(), None)
        tank.init_logging()
        self.foo = ConfigManager()
        (handler, name) = tempfile.mkstemp()
        self.foo.set_out_file(name)
    

    def tearDown(self):
        del self.foo
        self.foo = None

    def test_load_files(self):
        confs = ['config/load_1.conf', 'config/load_2.conf']
        self.foo.load_files(confs)
        self.foo.flush()
        
if __name__ == '__main__':
    unittest.main()

