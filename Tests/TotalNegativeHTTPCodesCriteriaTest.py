from Tank.Core import TankCore
from Tank.Plugins.Aggregator import AggregatorPlugin, SecondAggregateData
from Tank.Plugins.Autostop import AutostopPlugin
from Tests.TankTests import TankTestCase
from Tank.Plugins.TotalAutostop import TotalNegativeHTTPCodesCriteria
import os
import tempfile
import unittest


class TotalNegativeHTTPCodesCriteriaTest(TankTestCase):
    def setUp(self):
        self.relcriteria = TotalNegativeHTTPCodesCriteria(None, "2xx, 10%, 3s")
        self.abscriteria = TotalNegativeHTTPCodesCriteria(None, "20x, 30, 4s")

    def tearDown(self):
        del self.relcriteria
        self.relcriteria = None

        del self.abscriteria
        self.abscriteria = None

    def test_run_relative(self):
        data = list()
        for i in range(1,20):
            data = SecondAggregateData()
            data.overall.time = "2012-09-25 18:18:18"
            data.overall.RPS = 200 + 2*i
            data.overall.http_codes = {'200': 100, '201': 100, '501': i, '503': i}
            try:
                self.relcriteria.notify(data)
            except AttributeError:
                break
        if i != 13 : raise RuntimeError()

    def test_run_absolute(self):
        data = list()
        for i in range(1,20):
            data = SecondAggregateData()
            data.overall.time = "2012-09-25 18:18:18"
            data.overall.RPS = 200 + 2*i
            data.overall.http_codes = {'200': 100, '201': 100, '302': i*2}
            try:
                self.abscriteria.notify(data)
            except AttributeError:
                break
        if i != 6 : raise RuntimeError()

if __name__ == '__main__':
    unittest.main()