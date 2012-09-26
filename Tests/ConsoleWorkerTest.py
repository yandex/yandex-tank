from Tank.ConsoleWorker import ConsoleTank
from Tank.Plugins.ConsoleOnline import ConsoleOnlinePlugin
from Tests.ConsoleOnlinePluginTest import FakeConsoleMarkup
from Tests.TankTests import FakeOptions
import TankTests
import logging
import unittest


class  ConsoleWorkerTestCase(TankTests.TankTestCase):
    def setUp(self):
        opts = FakeOptions()
        opts.no_rc = False
        self.foo = ConsoleTank(opts, None)
        self.foo.set_baseconfigs_dir('full')

    def tearDown(self):
        del self.foo
        self.foo = None            

    def test_perform(self):
        self.foo.configure()

        console = self.foo.core.get_plugin_of_type(ConsoleOnlinePlugin)
        console.console_markup = FakeConsoleMarkup()
        
        if self.foo.perform_test() != 0:
            raise RuntimeError()
        
    def test_option_override(self):
        options = FakeOptions()
        options.config = ["config/old-style.conf"]
        options.option = ["owner.address=overridden"]
        self.foo = ConsoleTank(options, None)
        self.foo.configure()
        res = self.foo.core.get_option("owner", "address")
        logging.debug(res)
        self.assertEquals("overridden", res)


    def test_option_old_convert(self):
        options = FakeOptions()
        options.config = ["data/old_to_migrate.conf"]
        self.foo = ConsoleTank(options, None)
        self.foo.configure()

if __name__ == '__main__':
    unittest.main()
