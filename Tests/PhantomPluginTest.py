from Tank.Core import TankCore
from Tank.Plugins.Phantom import PhantomPlugin
from Tests.TankTests import TankTestCase
import os
import tempfile
import time
import unittest

class  PhantomPluginTestCase(TankTestCase):
    def setUp(self):
        core = TankCore()
        (handler, name) = tempfile.mkstemp()
        core.config.set_out_file(name)
        core.load_configs(['config/phantom.conf'])
        core.load_plugins()
        core.plugins_check_config()
        core.plugins_prepare_test()
        self.foo = PhantomPlugin(core)

    def tearDown(self):
        del self.foo
        self.foo = None
        if os.path.exists("ready_conf_phout.txt"):
            os.remove("ready_conf_phout.txt")

    def test_run(self):
        self.foo.core.set_option(PhantomPlugin.SECTION, "config", '')
        self.foo.configure()
        self.foo.prepare_test()
        self.foo.start_test()
        while self.foo.is_test_finished() < 0:
            self.foo.log.debug("Not finished")
            time.sleep(1)
        if self.foo.is_test_finished() != 0:
            raise RuntimeError("RC: %s" % self.foo.is_test_finished())
        self.foo.end_test(0)

    def test_run_ready_conf(self):
        self.foo.core.add_artifact_file("ready_conf_phout.txt")
        self.foo.configure()
        self.foo.prepare_test()
        self.foo.start_test()
        while self.foo.is_test_finished() < 0:
            self.foo.log.debug("Not finished")
            time.sleep(1)
        if self.foo.is_test_finished() != 0:
            raise RuntimeError("RC: %s" % self.foo.is_test_finished())
        self.foo.end_test(0)
        
    def test_run_interrupt(self):
        self.foo.configure()
        self.foo.prepare_test()
        self.foo.start_test()
        time.sleep(2)
        self.foo.end_test(0)

    def test_run_stepper_cache(self):
        self.foo.configure()
        self.foo.prepare_test()
        self.foo.prepare_test()
        
    def test_domain_name(self):
        self.foo.core.set_option('phantom', 'address', 'yandex.ru')
        self.foo.configure()

    def test_domain_name_fail(self):
        self.foo.core.set_option('phantom', 'address', 'ya.ru')
        try:
            self.foo.configure()
            raise RuntimeError()
        except:
            pass

if __name__ == '__main__':
    unittest.main()
