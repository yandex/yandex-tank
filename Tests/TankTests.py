import logging
import tempfile
import unittest
import sys

from Tank.Plugins.Aggregator import SecondAggregateData, \
    SecondAggregateDataTotalItem
from tankcore import TankCore


class TankTestCase(unittest.TestCase):
    '''
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s\t%(message)s")
    logger = logging.getLogger('')
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logger.debug("Starting Unit Test")
    '''

    def get_aggregate_data(self, filename):
        return SecondAggregateData(SecondAggregateDataTotalItem())

    def callback(self, data):
        self.data = SecondAggregateData(data)

    def get_core(self):
        """

        :rtype : TankCore
        """
        self.core = TankCore()
        self.core.artifacts_base_dir = tempfile.mkdtemp()
        self.core.artifacts_dir = self.core.artifacts_base_dir
        return self.core


class FakeOptions(object):
    log = ''
    verbose = True
    config = []
    option = ['testsection.testoption=testvalue']
    ignore_lock = True
    lock_fail = False
    no_rc = True
    manual_start = False
    scheduled_start = None
    lock_dir = None


if __name__=="__main__":
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s\t%(message)s")
    logger = logging.getLogger('')
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logger.debug("Starting Unit Test")
