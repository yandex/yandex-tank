import json

from Tank.API.client import TankAPIClient
from Tank.API.server import TankAPIHandler
from Tests.TankTests import TankTestCase


class TankAPIHandlerTestCase(TankTestCase):
    def setUp(self):
        self.obj = TankAPIHandler()

    def test_run(self):
        res = json.loads(self.obj.handle_get(TankAPIClient.INITIATE_TEST_JSON)[2])
        self.assertNotEquals("", res["ticket"])
        try:
            self.obj.handle_get(TankAPIClient.INITIATE_TEST_JSON + "?exclusive=1")
            self.fail()
        except ValueError:
            pass