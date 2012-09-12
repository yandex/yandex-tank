from Tank.Core import TankCore
from Tank.Plugins.DataUploader import DataUploaderPlugin, KSHMAPIClient
from Tests.TankTests import TankTestCase
import os
import tempfile
import unittest
import logging
import json
import time

class  DataUploaderPluginTestCase(TankTestCase):
    def setUp(self):
        core = TankCore()
        (handler, name) = tempfile.mkstemp()
        core.config.set_out_file(name)
        core.load_configs(['config/uploader.conf'])
        core.load_plugins()
        self.foo = DataUploaderPlugin(core)
        self.foo.api_client=FakeAPICLient()
        self.foo.api_client.get_results.append('[{"closed":"", "name": "test task"}]')
        self.foo.api_client.get_results.append('[{"success":1}]')
        self.foo.api_client.post_results.append('[{"job":'+str(time.time())+'}]')
        self.foo.api_client.post_results.append('[{"success":1}]')

    def tearDown(self):
        del self.foo
        self.foo = None

    def test_run(self):
        self.foo.configure()
        self.foo.prepare_test()
        self.foo.start_test()
        self.foo.end_test(0)


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
