import time
from collections import namedtuple
from tankcore import AbstractPlugin
import logging
from random import randint
import threading as th

Sample = namedtuple(
    'Sample', 'marker,threads,overallRT,httpCode,netCode,sent,received,connect,send,latency,receive,accuracy')


class LogGun(AbstractPlugin):
    SECTION = 'log_gun'

    def __init__(self, core):
        self.log = logging.getLogger(__name__)
        AbstractPlugin.__init__(self, core)
        param = self.get_option("param", '15')
        self.log.info('Initialized log gun for BFG with param = %s' % param)

    def shoot(self, missile, marker):
        self.log.debug("Missile: %s\n%s", marker, missile)
        rt = randint(2, 30000)
        data_item = Sample(
            marker,             # marker
            th.active_count(),  # threads
            rt,                 # overallRT
            0,                  # httpCode
            0,                  # netCode
            0,                  # sent
            0,                  # received
            0,                  # connect
            0,                  # send
            rt,                 # latency
            0,                  # receive
            0,                  # accuracy
        )
        return (int(time.time()), data_item)
