from Tank.Plugins.Aggregator import SecondAggregateData
from Tank.Plugins.TotalAutostop import TotalNetCodesCriteria
from Tests.TankTests import TankTestCase
import unittest


class TotalNetCodesCriteriaTest(TankTestCase):
    def setUp(self):
        self.relcriteria = TotalNetCodesCriteria(None, "110, 37%, 3s")
        self.abscriteria = TotalNetCodesCriteria(None, "71, 30, 2s")

    def tearDown(self):
        del self.relcriteria
        self.relcriteria = None

        del self.abscriteria
        self.abscriteria = None

    def test_run_relative(self):
        data = list()
        for i in range(1,20):
            data = SecondAggregateData()
            data.time = "2012-09-25 18:18:" + str(i)
            data.overall.RPS = 100 + i**2
            data.overall.net_codes = {'0': 100, '110': i**2}
            if self.relcriteria.notify(data) :
                break
        if i != 9 : raise RuntimeError()

    def test_run_absolute(self):
        data = list()
        for i in range(1,20):
            data = SecondAggregateData()
            data.time = "2012-09-25 18:18:18"
            data.overall.RPS = 100 + i**2 + i
            data.overall.net_codes = {'0': 100, '71': i**2, '110' : i}
            if self.abscriteria.notify(data) :
                break
        if i != 5 : raise RuntimeError()


if __name__ == '__main__':
    unittest.main()

