from Tank.Plugins.Aggregator import SecondAggregateData, AggregatorPlugin
import os
import logging
from Tests.TankTests import TankTestCase

class  SecondAggregateDataTestCase(TankTestCase):
    data = None
    
    def test_simple(self):
        fh = open('data/preproc_single.txt', 'r')
        aggregator = AggregatorPlugin(None)
        
        aggregator.read_preproc_lines(fh, self.callback)
        self.foo = self.data
        
        
        logging.info("Data overall: %s", self.foo.overall)
        self.assertNotEqual(None, self.foo.overall)
        logging.info("Data cases: %s", self.foo.cases)
        self.assertEquals(8, len(self.foo.cases))
        self.assertNotEqual(None, self.foo.time)
        self.assertNotEqual(None, self.foo.overall.selfload)

    def test_simple_additional(self):
        fh = open('data/preproc_single2.txt', 'r')
        aggregator = AggregatorPlugin(None)
        
        aggregator.read_preproc_lines(fh, self.callback)
        self.foo = self.data
        
        
        logging.info("Data overall: %s", self.foo.overall)
        self.assertNotEqual(None, self.foo.overall)
        logging.info("Data cases: %s", self.foo.cases)
        self.assertEquals(8, len(self.foo.cases))
        self.assertNotEqual(None, self.foo.time)
        self.assertNotEqual(None, self.foo.overall.selfload)
        
    def callback(self, data):
        self.data = SecondAggregateData(data)
