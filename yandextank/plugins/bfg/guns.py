import time
from collections import namedtuple
from yandextank.core import AbstractPlugin
import logging
from random import randint
import threading as th
import sys

from sqlalchemy import create_engine
from sqlalchemy import exc

import requests

requests_logger = logging.getLogger('requests')
requests_logger.setLevel(logging.WARNING)

Sample = namedtuple(
    'Sample', 'marker,threads,overallRT,httpCode,netCode,sent,received,connect,send,latency,receive,accuracy')

from contextlib import contextmanager


@contextmanager
def measure(marker, err, results):
    start_time = time.time()
    yield
    response_time = int((time.time() - start_time) * 1000)
    data_item = Sample(
        marker,             # marker
        th.active_count(),  # threads
        response_time,      # overall response time
        err,                # httpCode
        0,                  # netCode
        0,                  # sent
        0,                  # received
        0,                  # connect
        0,                  # send
        response_time,      # latency
        0,                  # receive
        0,                  # accuracy
    )
    results.put((int(time.time()), data_item), timeout=1)


class LogGun(AbstractPlugin):
    SECTION = 'log_gun'

    def __init__(self, core):
        self.log = logging.getLogger(__name__)
        AbstractPlugin.__init__(self, core)
        param = self.get_option("param", '15')
        self.log.info('Initialized log gun for BFG with param = %s' % param)

    def shoot(self, missile, marker, results):
        self.log.info("Missile: %s\n%s", marker, missile)
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
        results.put((int(time.time()), data_item), timeout=1)

class SqlGun(AbstractPlugin):
    SECTION = 'sql_gun'

    def __init__(self, core):
        self.log = logging.getLogger(__name__)
        AbstractPlugin.__init__(self, core)
        self.engine = create_engine(self.get_option("db"))

    def shoot(self, missile, marker, results):
        self.log.debug("Missile: %s\n%s", marker, missile)
        start_time = time.time()
        errno = 0
        httpCode = 200
        try:
            cursor = self.engine.execute(missile.replace('%', '%%'))
            cursor.fetchall()
            cursor.close()
        except exc.TimeoutError as e:
            self.log.debug("Timeout: %s", e)
            errno = 110
        except exc.ResourceClosedError as e:
            self.log.debug(e)
        except exc.SQLAlchemyError as e:
            httpCode = 500
            self.log.debug(e.orig.args)
        except exc.SAWarning as e:
            httpCode = 400
            self.log.debug(e)
        except Exception as e:
            httpCode = 500
            self.log.debug(e)
        rt = int((time.time() - start_time) * 1000)
        data_item = Sample(
            marker,             # marker
            th.active_count(),  # threads
            rt,                 # overallRT
            httpCode,           # httpCode
            errno,              # netCode
            0,                  # sent
            0,                  # received
            0,                  # connect
            0,                  # send
            rt,                 # latency
            0,                  # receive
            0,                  # accuracy
        )
        results.put((int(time.time()), data_item), timeout=1)

class CustomGun(AbstractPlugin):
    SECTION = 'custom_gun'

    def __init__(self, core):
        self.log = logging.getLogger(__name__)
        AbstractPlugin.__init__(self, core)
        module_path = self.get_option("module_path")
        module_name = self.get_option("module_name")
        sys.path.append(module_path)
        self.module = __import__(module_name)

    def shoot(self, missile, marker, results):
        results.put(self.module.shoot(self, missile, marker), timeout=1)

class HttpGun(AbstractPlugin):
    SECTION = 'http_gun'

    def __init__(self, core):
        self.log = logging.getLogger(__name__)
        AbstractPlugin.__init__(self, core)
        self.base_address = self.get_option("base_address")

    def shoot(self, missile, marker, results):
        self.log.debug("Missile: %s\n%s", marker, missile)
        start_time = time.time()
        r = requests.get(self.base_address + missile)
        errno = 0
        httpCode = r.status_code
        rt = int((time.time() - start_time) * 1000)
        data_item = Sample(
            marker,             # marker
            th.active_count(),  # threads
            rt,                 # overallRT
            httpCode,           # httpCode
            errno,              # netCode
            0,                  # sent
            0,                  # received
            0,                  # connect
            0,                  # send
            rt,                 # latency
            0,                  # receive
            0,                  # accuracy
        )
        results.put((int(time.time()), data_item), timeout=1)

class ScenarioGun(AbstractPlugin):
    SECTION = 'scenario_gun'

    def __init__(self, core):
        self.log = logging.getLogger(__name__)
        AbstractPlugin.__init__(self, core)

    def shoot(self, missile, marker, results):
        err = 0
        with measure("root", err, results):
            #resp = requests.get("http://bsgraphite-gfe01h.yandex.ru/")
            #err = resp.status_code
            time.sleep(1)
        with measure("afdb_load", err, results):
            #resp = requests.get("http://bsgraphite-gfe01h.yandex.ru/afdb_load/")
            #err = resp.status_code
            time.sleep(1)
        with measure("afdb", err, results):
            #resp = requests.get("http://bsgraphite-gfe01h.yandex.ru/afdb/")
            #err = resp.status_code
            time.sleep(1)
