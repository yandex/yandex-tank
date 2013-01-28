from Tank.Plugins.Phantom import PhantomConfig, PhantomPlugin
from Tests.TankTests import TankTestCase
import unittest
import logging
from Tank.Plugins.PhantomUtils import StepperWrapper

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
        conf_str = open(config).read()
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
        info=foo.get_info()
        logging.info(info.steps)
        self.assertEquals(len(info.steps), 450)
        
        conf_str = open(config).read()
        logging.info(conf_str)
        self.assertEquals(conf_str.count("io_benchmark_t"), 3)
        self.assertEquals(conf_str.count("benchmark_io "), 2)
        self.assertEquals(conf_str.count("benchmark_io1 "), 2)
        self.assertEquals(conf_str.count("benchmark_io2 "), 2)
        

    def test_multiload_parsing(self):
        core = self.get_core()
        foo = StepperWrapper(core, PhantomPlugin.SECTION)
        foo.core.set_option('phantom', 'rps_schedule', 'const(1,1) line(1,100,60)\nstep(1,10,1,10)')
        foo.read_config()
        self.assertEquals(['const(1,1)', 'line(1,100,60)', 'step(1,10,1,10)'], foo.rps_schedule)
    
    

if __name__ == '__main__':
    unittest.main()
