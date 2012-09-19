from Tank.Plugins.Aggregator import SecondAggregateData, AggregatorPlugin
from Tests.TankTests import TankTestCase
import logging
import os

class  SecondAggregateDataTestCase(TankTestCase):
    def test_simple(self):
        self.foo = self.get_aggregate_data('data/preproc_single.txt')
        
        
        logging.info("Data overall: %s", self.foo.overall)
        self.assertNotEqual(None, self.foo.overall)
        logging.info("Data cases: %s", self.foo.cases)
        self.assertEquals(8, len(self.foo.cases))
        self.assertNotEqual(None, self.foo.time)
        self.assertNotEqual(None, self.foo.overall.selfload)

    def test_simple_additional(self):
        self.foo = self.get_aggregate_data('data/preproc_single2.txt')
        
        logging.info("Data overall: %s", self.foo.overall)
        self.assertNotEqual(None, self.foo.overall)
        logging.info("Data cases: %s", self.foo.cases)
        self.assertEquals(8, len(self.foo.cases))
        self.assertNotEqual(None, self.foo.time)
        self.assertNotEqual(None, self.foo.overall.selfload)
