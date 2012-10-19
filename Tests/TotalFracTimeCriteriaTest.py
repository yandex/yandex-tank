from Tank.Plugins.Aggregator import SecondAggregateData
from Tank.Plugins.TotalAutostop import TotalFracTimeCriteria
from Tests.TankTests import TankTestCase
import unittest


class TotalFracTimeCriteriaTest(TankTestCase):
    def setUp(self):
        self.criteria = TotalFracTimeCriteria(None, "10ms, 50%, 3s")

    def tearDown(self):
        del self.criteria
        self.criteria = None
    def test_null(self):
        data = list()
        for i in range(0,20):
            data = SecondAggregateData()
            data.time = "2012-09-25 18:18:" + str(i)

            if i%5 != 0:
                data.overall.times_dist = [
                    {'count': 10, 'to': 10, 'from': 0},
                    {'count': i+1, 'to': 20, 'from': 10}]
            try:
                self.criteria.notify(data)
            except:
                break
        if i != 13 : raise RuntimeError()

    def test_run(self):
        data = list()
        for i in range(0,20):
            data = SecondAggregateData()
            data.time = "2012-09-25 18:18:18"
            data.overall.times_dist = [
                {'count': 10, 'to': 10, 'from': 0},
                {'count': i+1, 'to': 20, 'from': 10}]
            try:
                self.criteria.notify(data)
            except:
                break
        if i != 11 : raise RuntimeError()

if __name__ == '__main__':
    unittest.main()

