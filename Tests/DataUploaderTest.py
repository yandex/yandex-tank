from Tank.Core import TankCore
from Tank.Plugins.DataUploader import DataUploaderPlugin, KSHMAPIClient
from Tests.TankTests import TankTestCase
import tempfile
import unittest
import logging
import json
import time

class  DataUploaderPluginTestCase(TankTestCase):
    def setUp(self):
        core = self.get_core()
        name = tempfile.mkstemp()[1]
        core.config.set_out_file(name)
        core.load_configs(['config/uploader.conf'])
        core.load_plugins()
        self.foo = DataUploaderPlugin(core)
        self.foo.api_client = FakeAPICLient()
        self.foo.api_client.get_results.append('[{"closed":"", "name": "test task"}]')
        self.foo.api_client.get_results.append('[{"success":1}]')
        self.foo.api_client.post_results.append('[{"job":' + str(time.time()) + '}]')
        self.foo.api_client.post_results.append('[{"success":1}]')

    def tearDown(self):
        del self.foo
        self.foo = None

    def test_run(self):
        self.foo.configure()
        self.foo.prepare_test()
        self.foo.start_test()
        self.foo.end_test(0)

    def test_run_no_operator(self):
        self.foo.set_option("operator", '')
        self.foo.configure()
        self.assertNotEquals('', self.foo.operator)

if __name__ == '__main__':
    unittest.main()


class FakeAPICLient(KSHMAPIClient):
    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.get_results = []
        self.post_results = []
    
    def get(self, addr):
        return json.loads(self.get_results.pop(0))

    def post(self, addr, data):
        return json.loads(self.post_results.pop(0))
