import logging
import os
import time

from Tank.Plugins.Distributed import DistributedPlugin
from Tests.TankTests import TankTestCase
from Tank.API.client import TankAPIClient


class DistributedPluginTestCase(TankTestCase):
    def setUp(self):
        self.core = self.get_core()
        self.core.load_configs([os.path.dirname(__file__) + '/config/distributed.ini'])
        self.foo = DistributedPlugin(self.core)
        self.foo.api_client_class = FakeAPIClient

    def test_run(self):
        self.foo.configure()

        for mock in self.foo.api_clients:
            mock.get_data.append(Exception("Some error"))
            mock.get_data.append({"ticket": str(time.time())})
            mock.post_data.append({})
            mock.get_data.append({"status": TankAPIClient.PREPARING, "exclusive": 1})
            mock.get_data.append({"status": TankAPIClient.PREPARED, "exclusive": 1})

            mock.get_data.append({})
            mock.get_data.append({"status": TankAPIClient.RUNNING, "exclusive": 1})
            mock.get_data.append({"status": TankAPIClient.FINISHING, "exclusive": 1})
            mock.get_data.append({"status": TankAPIClient.FINISHING, "exclusive": 1})
            mock.get_data.append({"status": TankAPIClient.FINISHED, "exclusive": 1})
            mock.get_data.append({"status": TankAPIClient.FINISHED, "artifacts": ["tank.log", "test.log", "phout.txt"]})
            mock.get_data.append("some content")
            mock.get_data.append("some more content")

        self.foo.prepare_test()
        self.foo.start_test()
        self.assertEquals(-1, self.foo.is_test_finished())
        self.assertEquals(0, self.foo.is_test_finished())
        self.foo.end_test(0)
        self.foo.post_process(0)


class FakeAPIClient(TankAPIClient):
    def __init__(self, address, to):
        TankAPIClient.__init__(self, address, to)
        logging.debug("Fake API client for %s", address)
        self.get_data = []
        self.post_data = []

    def query_get(self, url, params=None):
        logging.debug(" Mocking GET request: %s with %s", url, params)
        resp = self.get_data.pop(0)
        logging.debug("Mocking GET response: %s", resp)
        if isinstance(resp, Exception):
            raise resp
        return resp

    def query_post(self, url, params=None, body=None):
        logging.debug(" Mocking POST request: %s with %s, body:\n%s", url, params, body)
        resp = self.post_data.pop(0)
        logging.debug("Mocking POST response: %s", resp)
        if isinstance(resp, Exception):
            raise resp
        return resp

    def query_get_to_file(self, url, params, local_name):
        resp = self.query_get(url, params)
        logging.debug("Saving data to %s", local_name)
        with open(local_name, "wb") as fd:
            fd.write("%s" % resp)
