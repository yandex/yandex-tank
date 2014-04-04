import logging
import os
import random

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
        self.foo.prepare_test()
        self.foo.start_test()
        self.foo.is_test_finished()
        self.foo.end_test(0)
        self.foo.post_process(0)


class FakeAPIClient(TankAPIClient):
    def __init__(self, address, port, to):
        TankAPIClient.__init__(self, address, port, to)
        logging.debug("Fake API client for %s", address)

    def get_status(self):
        status = int(random.random() * 4)
        logging.debug("Mocking status for %s: %s", self, status)
        return status

    def book(self):
        return True