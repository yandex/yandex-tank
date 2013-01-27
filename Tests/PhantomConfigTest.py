from Tank.Plugins.Phantom import PhantomConfig
from Tests.TankTests import TankTestCase
import unittest
import logging

class  PhantomConfigTestCase(TankTestCase):
    def setUp(self):
        pass

    def test_simple(self):
        core = self.get_core()
        core.load_configs(['config/phantom.conf'])
        core.load_plugins()
        core.plugins_configure()
        core.plugins_prepare_test()
        
        foo = PhantomConfig(core)
        foo.read_config()
        config = foo.compose_config()
        conf_str=open(config).read()
        logging.info(conf_str)
        self.assertEquals(conf_str.count("io_benchmark_t"), 1)
        
    def test_double(self):
        core = self.get_core()
        core.load_configs(['config/phantom_double.conf'])
        core.load_plugins()
        core.plugins_configure()
        core.plugins_prepare_test()
        
        foo = PhantomConfig(core)
        foo.read_config()
        config = foo.compose_config()
        conf_str=open(config).read()
        logging.info(conf_str)
        self.assertEquals(conf_str.count("io_benchmark_t"), 2)

if __name__ == '__main__':
    unittest.main()
