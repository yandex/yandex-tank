import TankTests
import os
import unittest
from Tank.ConsoleWorker import ConsoleTank
from Tests.TankTests import FakeOptions
from Tank.Plugins.DataUploader import DataUploaderPlugin
from Tests.DataUploaderTest import FakeAPICLient
from Tank.Plugins.ConsoleOnline import ConsoleOnlinePlugin
from Tests.ConsoleOnlinePluginTest import FakeConsoleMarkup
import time
import logging


class  ConsoleWorkerTestCase(TankTests.TankTestCase):
    def setUp(self):
        self.foo = ConsoleTank(FakeOptions(), None)
        self.foo.set_baseconfigs_dir('full')

    def tearDown(self):
        del self.foo
        self.foo = None
        try:
            os.remove('lp.conf')
        except:
            pass
        try:
            os.remove('lunapark.log')
        except:
            pass
            

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

if __name__ == '__main__':
    unittest.main()
