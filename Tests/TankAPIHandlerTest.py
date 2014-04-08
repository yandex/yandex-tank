import json
from mimetools import Message
from urllib2 import HTTPError

from Tank.API.client import TankAPIClient

from Tank.API.server import TankAPIHandler
from Tests.TankTests import TankTestCase


class TankAPIHandlerTestCase(TankTestCase):
    def setUp(self):
        self.obj = TankAPIHandler()

    def test_run_usual(self):
        res = json.loads(self.obj.handle_get(TankAPIClient.INITIATE_TEST_JSON)[2])
        self.assertNotEquals("", res["ticket"])
        res = json.loads(self.obj.handle_get(TankAPIClient.TEST_STATUS_JSON + "?ticket=" + res["ticket"])[2])
        self.assertEquals(TankAPIClient.BOOKED, res["status"])
        fd = open("data/post.txt")

        message = Message(fd)
        message.parsetype()
        self.obj.handle_post(TankAPIClient.PREPARE_TEST_JSON + "?ticket=" + res["ticket"], message, fd)

    def test_run_booking(self):
        res = json.loads(self.obj.handle_get(TankAPIClient.INITIATE_TEST_JSON)[2])
        self.assertNotEquals("", res["ticket"])
        try:
            self.obj.handle_get(TankAPIClient.INITIATE_TEST_JSON + "?exclusive=1")
            self.fail()
        except HTTPError, exc:
            self.assertEqual(423, exc.getcode())

        self.obj.handle_get(TankAPIClient.INTERRUPT_TEST_JSON + "?ticket=" + res["ticket"])
        self.obj.handle_get(TankAPIClient.INTERRUPT_TEST_JSON + "?ticket=" + res["ticket"])


def record_post(handler):
    with open("post.txt", "wb") as fd:
        fd.write(handler.raw_requestline)
        fd.write(str(handler.headers) + "\r\n")
        while True:
            fd.write(handler.rfile.read(1))
            fd.flush()
