import json
import logging
from mimetools import Message
import unittest
from urllib2 import HTTPError
import time

from Tank.API.client import TankAPIClient
from Tank.API.server import TankAPIHandler
from Tests.TankTests import TankTestCase


class TankAPIHandlerTestCase(TankTestCase):
    def setUp(self):
        self.obj = TankAPIHandler()

    def test_run_usual(self):
        res = json.loads(self.obj.handle_get(TankAPIClient.INITIATE_TEST_JSON)[2])
        ticket = res['ticket']
        self.assertNotEquals("", ticket)
        res = json.loads(self.obj.handle_get(TankAPIClient.TEST_STATUS_JSON + "?ticket=" + ticket)[2])
        self.assertEquals(TankAPIClient.STATUS_BOOKED, res["status"])
        fd = open("data/post.txt")

        message = Message(fd)
        message.parsetype()
        self.obj.handle_post(TankAPIClient.PREPARE_TEST_JSON + "?ticket=" + ticket, message, fd)
        while True:
            res = json.loads(self.obj.handle_get(TankAPIClient.TEST_STATUS_JSON + "?ticket=" + ticket)[2])
            if res['status'] != TankAPIClient.STATUS_PREPARING:
                break
            time.sleep(1)

        self.assertEqual(TankAPIClient.STATUS_PREPARED, res['status'])

        self.obj.handle_get(TankAPIClient.START_TEST_JSON + "?ticket=" + ticket)

        res = self.obj.handle_get(TankAPIClient.TEST_DATA_STREAM_JSON + "?ticket=" + ticket)
        self.assertEqual(200, res[0])

        for _ in range(1, 10):
            res = json.loads(self.obj.handle_get(TankAPIClient.TEST_STATUS_JSON + "?ticket=" + ticket)[2])
            if res['status'] != TankAPIClient.STATUS_RUNNING:
                break
            time.sleep(1)

        self.obj.handle_get(TankAPIClient.INTERRUPT_TEST_JSON + "?ticket=" + ticket)
        while True:
            res = json.loads(self.obj.handle_get(TankAPIClient.TEST_STATUS_JSON + "?ticket=" + ticket)[2])
            if res['status'] == TankAPIClient.STATUS_FINISHED:
                break
            time.sleep(1)

        res = json.loads(self.obj.handle_get(TankAPIClient.TEST_STATUS_JSON + "?ticket=" + ticket)[2])
        artifacts = res['artifacts']
        art_cnt = 0
        for artifact in artifacts:
            url = TankAPIClient.DOWNLOAD_ARTIFACT_URL + "?ticket=" + ticket + "&filename=" + artifact
            res = self.obj.handle_get(url)
            logging.debug(res[2].read()[:64])
            art_cnt += 1
        self.assertEquals(9, art_cnt)

        res = self.obj.handle_get(TankAPIClient.TEST_DATA_STREAM_JSON + "?ticket=" + ticket)
        self.assertEqual(200, res[0])

    def test_run_booking(self):
        res = json.loads(self.obj.handle_get(TankAPIClient.INITIATE_TEST_JSON)[2])
        ticket = res["ticket"]
        self.assertNotEquals("", ticket)
        try:
            self.obj.handle_get(TankAPIClient.INITIATE_TEST_JSON + "?exclusive=1")
            self.fail()
        except HTTPError, exc:
            self.assertEqual(423, exc.getcode())

        res = json.loads(self.obj.handle_get(TankAPIClient.TANK_STATUS_JSON)[2])
        self.assertTrue(ticket in res["live_tickets"])

        self.obj.handle_get(TankAPIClient.INTERRUPT_TEST_JSON + "?ticket=" + ticket)
        try:
            self.obj.handle_get(TankAPIClient.INTERRUPT_TEST_JSON + "?ticket=" + ticket)
            self.fail()
        except HTTPError, exc:
            self.assertEqual(422, exc.getcode())


def record_post(handler):
    """

    :type handler: BaseHTTPRequestHandler
    """
    with open("post.txt", "wb") as fd:
        #fd.write(handler.raw_requestline)
        fd.write(str(handler.headers) + "\r\n")
        while True:
            fd.write(handler.rfile.read(1))
            fd.flush()


if __name__ == '__main__':
    unittest.main()
