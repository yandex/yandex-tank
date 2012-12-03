from Tank.Plugins.Aggregator import SecondAggregateData
from Tank.Plugins.TotalAutostop import TotalFracTimeCriteria, TotalHTTPCodesCriteria, TotalNegativeHTTPCodesCriteria, TotalNetCodesCriteria, TotalNegativeNetCodesCriteria, TotalHTTPTrendCriteria
from Tests.TankTests import TankTestCase
import unittest

class TotalCriteriasTest(TankTestCase):
    def setUp(self):
        self.frac_criteria = TotalFracTimeCriteria(None, "10ms, 50%, 3s")
        self.http_relcriteria = TotalHTTPCodesCriteria(None, "50x, 10%, 3s")
        self.http_abscriteria = TotalHTTPCodesCriteria(None, "50x, 30, 4s")
        self.negative_http_relcriteria = TotalNegativeHTTPCodesCriteria(None, "2xx, 10%, 3s")
        self.negative_http_abscriteria = TotalNegativeHTTPCodesCriteria(None, "20x, 30, 4s")
        self.net_relcriteria = TotalNetCodesCriteria(None, "110, 37%, 3s")
        self.net_abscriteria = TotalNetCodesCriteria(None, "71, 30, 2s")
        self.negative_net_relcriteria = TotalNegativeNetCodesCriteria(None, "0, 45%, 5s")
        self.negative_net_abscriteria = TotalNegativeNetCodesCriteria(None, "0, 100, 5s")

        self.http_trend = TotalHTTPTrendCriteria(None, "2xx, 10s")

    def tearDown(self):
        #frac time
        del self.frac_criteria
        self.frac_criteria = None

        #http
        del self.http_relcriteria
        self.http_relcriteria = None
        del self.http_abscriteria
        self.http_abscriteria = None

        #negative http
        del self.negative_http_relcriteria
        self.negative_http_relcriteria = None
        del self.negative_http_abscriteria
        self.negative_http_abscriteria = None

        #net
        del self.net_relcriteria
        self.net_relcriteria = None
        del self.net_abscriteria
        self.net_abscriteria = None

        #negative net
        del self.negative_net_relcriteria
        self.negative_net_relcriteria = None
        del self.negative_net_abscriteria
        self.negative_net_abscriteria = None

        #tangent of total_count
        del self.http_trend
        self.http_trend = None

    def test_frac_null(self):
        data = list()
        for i in range(0,20):
            data = SecondAggregateData()
            data.time = "2012-09-25 18:18:18"

            if i%5 != 0:
                data.overall.times_dist = [
                    {'count': 10, 'to': 10, 'from': 0},
                    {'count': i+1, 'to': 20, 'from': 10}]
            if self.frac_criteria.notify(data) :
                break
        if i != 13 :
                raise RuntimeError();

    def test_frac_run(self):
        data = list()
        for i in range(0,20):
            data = SecondAggregateData()
            data.time = "2012-09-25 18:18:18"
            data.overall.times_dist = [
                {'count': 10, 'to': 10, 'from': 0},
                {'count': i+1, 'to': 20, 'from': 10}]
            if self.frac_criteria.notify(data):
                break
        if i != 11 :
            raise RuntimeError()

    def test_http_run_relative(self):
        data = list()
        for i in range(1,20):
            data = SecondAggregateData()
            data.time = "2012-09-25 18:18:18"
            data.overall.RPS = 100 + i*2
            data.overall.http_codes = {'200': 100, '501': i, '503': i}
            if self.http_relcriteria.notify(data):
                break
        if i != 7 : raise RuntimeError()

    def test_http_run_absolute(self):
        data = list()
        for i in range(1,20):
            data = SecondAggregateData()
            data.time = "2012-09-25 18:18:18"
            data.overall.RPS = 100 + i*2
            data.overall.http_codes = {'200': 100, '501': i, '503': i}
            if self.http_abscriteria.notify(data) :
                break
        if i != 6 : raise RuntimeError()

    def test_negative_http_run_relative(self):
        data = list()
        for i in range(1,20):
            data = SecondAggregateData()
            data.time = "2012-09-25 18:18:18"
            data.overall.RPS = 200 + 2*i
            data.overall.http_codes = {'200': 100, '201': 100, '501': i, '503': i}
            if self.negative_http_relcriteria.notify(data):
                break
        if i != 13 : raise RuntimeError()

    def test_negative_http_run_absolute(self):
        data = list()
        for i in range(1,20):
            data = SecondAggregateData()
            data.time = "2012-09-25 18:18:18"
            data.overall.RPS = 200 + 2*i
            data.overall.http_codes = {'200': 100, '201': 100, '302': i*2}
            if self.negative_http_abscriteria.notify(data) :
                break
        if i != 6 : raise RuntimeError()

    def test_net_run_relative(self):
        data = list()
        for i in range(1,20):
            data = SecondAggregateData()
            data.time = "2012-09-25 18:18:18"
            data.overall.RPS = 100 + i**2
            data.overall.net_codes = {'0': 100, '110': i**2}
            if self.net_relcriteria.notify(data) :
                break
        if i != 9 : raise RuntimeError()

    def test_net_run_absolute(self):
        data = list()
        for i in range(1,20):
            data = SecondAggregateData()
            data.time = "2012-09-25 18:18:18"
            data.overall.RPS = 100 + i**2 + i
            data.overall.net_codes = {'0': 100, '71': i**2, '110' : i}
            if self.net_abscriteria.notify(data) :
                break
        if i != 5 : raise RuntimeError()

    def test_negative_net_run_relative(self):
        data = list()
        for i in range(1,20):
            data = SecondAggregateData()
            data.time = "2012-09-25 18:18:18"
            data.overall.RPS = 100 + i**2
            data.overall.net_codes = {'0': 100, '110': i**2}
            if self.negative_net_relcriteria.notify(data) :
                break
        if i != 12 : raise RuntimeError()

    def test_negative_net_run_absolute(self):
        data = list()
        for i in range(1,20):
            data = SecondAggregateData()
            data.time = "2012-09-25 18:18:18"
            data.overall.RPS = 100 + i**2
            data.overall.net_codes = {'0': 100, '110': i**2}
            if self.negative_net_abscriteria.notify(data) :
                break
        if i != 7 : raise RuntimeError()

    def test_http_trend_run(self):
        data = list()
        for i in range(1,30):
            data = SecondAggregateData()
            data.time = "2012-09-25 18:18:18"
            data.overall.RPS = 200
            
            if i < 10 :
                data.overall.RPS += i
                data.overall.http_codes = {'200': 100+i, '201': 100}

            elif i >= 10 and i < 20:
                if i % 2:
                    diff = -3
                else :
                    diff = 3

                data.overall.RPS += 10 + diff
                data.overall.http_codes = {'200': 110 + diff, '201': 100}

            elif i >= 20 and i < 30:
                diff = i - 20
                data.overall.RPS += 10 - diff + i
                data.overall.http_codes = {'200': 110 - diff, '201': 100, '502': i}

            if self.http_trend.notify(data) :
                break
        
        if i != 28 : 
             raise RuntimeError()

if __name__ == '__main__':
    unittest.main()

