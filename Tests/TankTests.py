import logging
import unittest
import sys
from Tank.Plugins.Aggregator import AggregatorPlugin, SecondAggregateData,\
    SecondAggregateDataTotalItem

class TankTestCase(unittest.TestCase):
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s\t%(message)s")
    logger = logging.getLogger('')
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logger.debug("Starting Unit Test")

    def get_aggregate_data(self, filename):
        return SecondAggregateData(SecondAggregateDataTotalItem())
        
    def callback(self, data):
        self.data = SecondAggregateData(data, SecondAggregateDataTotalItem())


class FakeOptions(object):
    log = ''
    verbose = True
    config = []
    option = ['testsection.testoption=testvalue']
    ignore_lock = True
    lock_fail = False
    
