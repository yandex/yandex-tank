from Tank.Plugins.Aggregator import SecondAggregateData
from Tank.Plugins.TotalAutostop import TotalHTTPCodesCriteria
from Tests.TankTests import TankTestCase
import unittest


class TotalHTTPCodesCriteriaTest(TankTestCase):
    def setUp(self):
        self.relcriteria = TotalHTTPCodesCriteria(None, "50x, 10%, 3s")
        self.abscriteria = TotalHTTPCodesCriteria(None, "50x, 30, 4s")

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
            data.overall.RPS = 100 + i*2
            data.overall.http_codes = {'200': 100, '501': i, '503': i}
            try:
                self.relcriteria.notify(data)
            except AttributeError:
                break
        if i != 7 : raise RuntimeError()

    def test_run_absolute(self):
        data = list()
        for i in range(1,20):
            data = SecondAggregateData()
            data.overall.time = "2012-09-25 18:18:18"
            data.overall.RPS = 100 + i*2
            data.overall.http_codes = {'200': 100, '501': i, '503': i}
            try:
                self.abscriteria.notify(data)
            except AttributeError:
                break
        if i != 6 : raise RuntimeError()


if __name__ == '__main__':
    unittest.main()