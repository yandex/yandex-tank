from yandextank.core.consoleworker import ConsoleTank
from yandextank.plugins.ConsoleOnline import ConsoleOnlinePlugin
from ConsoleOnlinePluginTest import FakeConsoleMarkup
from TankTests import FakeOptions
import TankTests
import logging
import unittest
import datetime


class ConsoleWorkerTestCase(TankTests.TankTestCase):

    def setUp(self):
        opts = FakeOptions()
        opts.no_rc = False
        opts.scheduled_start = datetime.datetime.now().strftime('%H:%M:%S')
        self.foo = ConsoleTank(opts, None)
        self.foo.set_baseconfigs_dir('full')

    def tearDown(self):
        del self.foo
        self.foo = None

    def test_perform(self):
        self.foo.configure()

        try:
            console = self.foo.core.get_plugin_of_type(ConsoleOnlinePlugin)
            console.console_markup = FakeConsoleMarkup()
        except:
            pass

        if self.foo.perform_test() != 0:
            raise RuntimeError()

    def test_option_override(self):
        options = FakeOptions()
        options.config = ["config/phantom.conf"]
        options.option = ["owner.address=overridden"]
        self.foo = ConsoleTank(options, None)
        self.foo.configure()
        res = self.foo.core.get_option("owner", "address")
        logging.debug(res)
        self.assertEquals("overridden", res)


if __name__ == '__main__':
    unittest.main()
