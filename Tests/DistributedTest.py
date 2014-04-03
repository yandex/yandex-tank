import os

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


class FakeAPIClient(TankAPIClient):
    def __init__(self):
        TankAPIClient.__init__(self)