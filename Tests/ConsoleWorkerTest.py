from Tank.ConsoleWorker import ConsoleTank
from Tank.Plugins.ConsoleOnline import ConsoleOnlinePlugin
from Tank.Plugins.DataUploader import DataUploaderPlugin
from Tests.ConsoleOnlinePluginTest import FakeConsoleMarkup
from Tests.DataUploaderTest import FakeAPICLient
from Tests.TankTests import FakeOptions
import TankTests
import logging
import time
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

        uploader = self.foo.core.get_plugin_of_type(DataUploaderPlugin)
        uploader.api_client = FakeAPICLient()
        uploader.api_client.get_results.append('[{"closed":"", "name": "test task"}]')
        uploader.api_client.get_results.append('[{"success":1}]')
        uploader.api_client.post_results.append('[{"job":' + str(time.time()) + '}]')
        for n in range(1, 120):
            uploader.api_client.post_results.append('[{"success":1}]')

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
