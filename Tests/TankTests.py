import logging
import unittest
import sys

class TankTestCase(unittest.TestCase):
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s\t%(message)s")
    logger = logging.getLogger('')
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logger.debug("Starting Unit Test")


class FakeOptions(object):
    log = ''
    verbose = True
    config = []
    option = ['testsection.testoption=testvalue']
    ignore_lock = True
