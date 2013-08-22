import time
from collections import namedtuple
from tankcore import AbstractPlugin
import logging
from random import randint
import threading as th

from sqlalchemy import create_engine
from sqlalchemy import exc

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

class SqlGun(AbstractPlugin):
    SECTION = 'sql_gun'

    def __init__(self, core):
        self.log = logging.getLogger(__name__)
        AbstractPlugin.__init__(self, core)
        self.engine = create_engine(self.get_option("db"))

    def shoot(self, missile, marker):
        self.log.debug("Missile: %s\n%s", marker, missile)
        start_time = time.time()
        errno = 0
        httpCode = 200
        try:
            self.engine.execute(missile.replace('%', '%%')).fetchall()
        except exc.ResourceClosedError as e:
            pass
        except exc.SQLAlchemyError as e:
            errno = e.orig.args[0]
            self.log.warn(e.orig.args)
        rt = int((time.time() - start_time) * 1000)
        data_item = Sample(
            marker,             # marker
            th.active_count(),  # threads
            rt,                 # overallRT
            httpCode,                  # httpCode
            errno,                  # netCode
            0,                  # sent
            0,                  # received
            0,                  # connect
            0,                  # send
            rt,                 # latency
            0,                  # receive
            0,                  # accuracy
        )
        return (int(time.time()), data_item)