import datetime
import logging
import os
import time
import unittest
import urllib

from Tank.Plugins.Aggregator import AggregatorPlugin, SecondAggregateData
from Tank.Plugins.Distributed import DistributedPlugin, DistributedReader
from Tests.TankTests import TankTestCase
from Tank.API.client import TankAPIClient


class DistributedPluginTestCase(TankTestCase):
    def setUp(self):
        self.core = self.get_core()
        self.core.load_configs([os.path.dirname(__file__) + '/config/distributed.ini'])
        self.core.load_plugins()
        self.foo = DistributedPlugin(self.core)
        self.foo.api_client_class = FakeAPIClient

    def test_run_minimal(self):

        self.core = self.get_core()
        self.core.set_option(DistributedPlugin.SECTION, "tanks_pool", "localhost")
        self.foo = DistributedPlugin(self.core)
        self.foo.api_client_class = FakeAPIClient
        self.foo.configure()

        for mock in self.foo.api_clients:
            mock.get_data.append({"ticket": str(time.time())})
            mock.post_data.append({})
            mock.get_data.append({"status": TankAPIClient.STATUS_PREPARED, "exclusive": 1})

            mock.get_data.append({})
            mock.get_data.append({"status": TankAPIClient.STATUS_FINISHED, "exclusive": 1, "exitcode": 0})
            mock.get_data.append({"status": TankAPIClient.STATUS_FINISHED, "exclusive": 1, "exitcode": 0})
            mock.get_data.append({"status": TankAPIClient.STATUS_FINISHED, "exclusive": 1, "exitcode": 0})
            mock.get_data.append(
                {"status": TankAPIClient.STATUS_FINISHED, "exitcode": 0,
                 "artifacts": ["tank.log", "test.log", "phout.txt"]})

        self.foo.prepare_test()
        self.foo.start_test()
        self.assertEquals(-1, self.foo.is_test_finished())
        time.sleep(self.foo.retry_interval + 1)
        self.assertEquals(0, self.foo.is_test_finished())
        self.foo.end_test(0)
        self.foo.post_process(0)


    def test_run(self):
        self.foo.configure()

        for mock in self.foo.api_clients:
            mock.get_data.append(Exception("Some error"))
            mock.get_data.append({"ticket": str(time.time())})
            mock.post_data.append({})
            mock.get_data.append({"status": TankAPIClient.STATUS_PREPARING, "exclusive": 1})
            mock.get_data.append({"status": TankAPIClient.STATUS_PREPARED, "exclusive": 1})

            mock.get_data.append({})
            mock.get_data.append({"status": TankAPIClient.STATUS_RUNNING, "exclusive": 1})
            mock.get_data.append(str(SecondAggregateData()) + "\n" + str(SecondAggregateData()))
            mock.get_data.append({"status": TankAPIClient.STATUS_FINISHING, "exclusive": 1, "exitcode": 0, })
            mock.get_data.append({"status": TankAPIClient.STATUS_FINISHING, "exclusive": 1, "exitcode": 0, })
            mock.get_data.append({"status": TankAPIClient.STATUS_FINISHED, "exclusive": 1, "exitcode": 0, })
            mock.get_data.append({"status": TankAPIClient.STATUS_FINISHED, "exclusive": 1, "exitcode": 0, })
            mock.get_data.append(
                {"status": TankAPIClient.STATUS_FINISHED, "exitcode": 0,
                 "artifacts": ["tank.log", "test.log", "phout.txt"]})
            mock.get_data.append("some content")
            mock.get_data.append("some more content")

        self.foo.prepare_test()
        aggregator = self.core.get_plugin_of_type(AggregatorPlugin)

        self.foo.start_test()
        self.assertEquals(-1, self.foo.is_test_finished())
        time.sleep(self.foo.retry_interval + 1)
        aggregator.is_test_finished()
        self.assertEquals(0, self.foo.is_test_finished())
        self.foo.end_test(0)
        self.foo.post_process(0)

    def test_aggregator_reader(self):
        self.foo.running_tests = [FakeAPIClient("test1"), FakeAPIClient("test2"), FakeAPIClient("test3")]
        # - Not all starts at the time
        # - Not all end the same way
        # - may have gaps
        zero = SecondAggregateData()
        one = SecondAggregateData()
        one.overall.rps = 1
        two = SecondAggregateData()
        two.overall.rps = 2
        three = SecondAggregateData()
        three.overall.rps = 3

        self.foo.running_tests[0].get_data.append("")
        self.foo.running_tests[1].get_data.append("")
        self.foo.running_tests[2].get_data.append("")

        now = datetime.datetime.now()

        zero.time = now
        one.time = now
        two.time = now
        three.time = now

        one.time = now + datetime.timedelta(0, 2)
        self.foo.running_tests[0].get_data.append(str(one) + "\n")
        two.time = now + datetime.timedelta(0, 3)
        self.foo.running_tests[0].get_data.append(str(two) + "\n")
        three.time = now + datetime.timedelta(0, 4)
        self.foo.running_tests[0].get_data.append(str(three) + "\n")
        three.time = now + datetime.timedelta(0, 5)
        self.foo.running_tests[0].get_data.append(str(three) + "\n")
        self.foo.running_tests[0].get_data.append("")
        self.foo.running_tests[0].get_data.append("")
        self.foo.running_tests[0].get_data.append("")
        self.foo.running_tests[0].get_data.append("")

        self.foo.running_tests[1].get_data.append("")
        self.foo.running_tests[1].get_data.append("")
        one.time = now + datetime.timedelta(0, 4)
        self.foo.running_tests[1].get_data.append(str(one) + "\n")
        two.time = now + datetime.timedelta(0, 5)
        self.foo.running_tests[1].get_data.append(str(two) + "\n")
        three.time = now + datetime.timedelta(0, 6)
        self.foo.running_tests[1].get_data.append(str(three) + "\n")
        three.time = now + datetime.timedelta(0, 7)
        self.foo.running_tests[1].get_data.append(str(three) + "\n")
        self.foo.running_tests[1].get_data.append("")
        self.foo.running_tests[1].get_data.append("")

        self.foo.running_tests[2].get_data.append("")
        self.foo.running_tests[2].get_data.append("")
        self.foo.running_tests[2].get_data.append("")
        one.time = now + datetime.timedelta(0, 1)
        self.foo.running_tests[2].get_data.append(str(one) + "\n")
        two.time = now + datetime.timedelta(0, 2)
        self.foo.running_tests[2].get_data.append(str(two) + "\n")
        three.time = now + datetime.timedelta(0, 3)
        self.foo.running_tests[2].get_data.append(str(three) + "\n")
        three.time = now + datetime.timedelta(0, 4)
        self.foo.running_tests[2].get_data.append(str(three) + "\n")
        self.foo.running_tests[2].get_data.append("")

        # do test
        aggregator = AggregatorPlugin(self.foo.core)
        reader = DistributedReader(aggregator, self.foo)

        res0 = reader.get_next_sample()
        self.assertIsNone(res0)

        res1 = reader.get_next_sample()
        #self.assertIsNotNone(res1)
        #self.assertEquals(1, res1.overall.rps)

        res2 = reader.get_next_sample()
        #self.assertIsNotNone(res2)
        #self.assertEquals(2, res2.overall.rps)

        res3 = reader.get_next_sample()
        #self.assertIsNotNone(res3)
        #self.assertEquals(4, res3.overall.rps)

        res4 = reader.get_next_sample()
        #self.assertIsNotNone(res4)

        res5 = reader.get_next_sample()
        #self.assertIsNotNone(res5)

        res6 = reader.get_next_sample()
        #self.assertIsNotNone(res6)

        res7 = reader.get_next_sample()
        #self.assertIsNotNone(res6)

        res8 = reader.get_next_sample()
        self.assertIsNone(res8)


class FakeAPIClient(TankAPIClient):
    def __init__(self, address):
        TankAPIClient.__init__(self, address, 1)
        logging.debug("Fake API client for %s", address)
        self.get_data = []
        self.post_data = []
        self.text_data = []

    def query_get_text(self, url, params=None):
        if params:
            url += "?" + urllib.urlencode(params)
        logging.debug(" Mocking GET request: %s", url)
        resp = self.get_data.pop(0)
        logging.debug("Mocking GET response: %s", resp)
        if isinstance(resp, Exception):
            raise resp
        return resp

    def query_get(self, url, params=None):
        return self.query_get_text(url, params)

    def query_post(self, url, params=None, ct=None, body=None):
        logging.debug(" Mocking POST request: %s with %s, body[%s]:\n%s", url, params, ct, body)
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


if __name__ == '__main__':
    unittest.main()
