# coding: utf-8

import sys
import json
import socket
import getpass
import urllib2
import traceback


__all__ = ["VERSION", "USER_AGENT", "USER_AGENT_PREFIX",
           "HOSTNAME_HEADER", "USERNAME_HEADER",
           "Transport", "adjust_timestamp"]

VERSION = "0.5.2"
USER_AGENT_PREFIX = "yasmapi/"
USER_AGENT = "yasmapi/" + VERSION
HOSTNAME_HEADER = "X-Golovan-Hostname"
USERNAME_HEADER = "X-Golovan-Username"


def adjust_timestamp(ts, period):
    return int(ts - (ts % period))


class Transport(object):
    """
    Класс реализует непосредственую коммуникацию с yasmfront.

    :param str golovan_host: Хост и опционально порт через `:` до yasmfront
    :param int connect_timeout: По истечении данного количества секунд
                                во время подключения к хосту, будет
                                поднято исключение socket.timeout
    """

    DEFAULT_GOLOVAN_HOST = "yasm.yandex-team.ru"
    DEFAULT_CONNECT_TIMEOUT = 25

    def __init__(self, golovan_host=None, connect_timeout=None):
        self.golovan_host = golovan_host if golovan_host else self.DEFAULT_GOLOVAN_HOST
        self.connect_timeout = connect_timeout if connect_timeout else self.DEFAULT_CONNECT_TIMEOUT

    def request(self, request, path):
        try:
            request = json.dumps(request)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            request = json.dumps({})

        headers = {"Content-Type": "application/json",
                   "User-Agent": USER_AGENT,
                   HOSTNAME_HEADER: socket.gethostname(),
        }

        try:
            headers[USERNAME_HEADER] = getpass.getuser()
        except Exception:
            pass

        req = urllib2.Request("http://%s/%s/" % (self.golovan_host, path),
                              request, headers)
        response = urllib2.urlopen(req, timeout=self.connect_timeout)

        try:
            r = response.read()
            resp = json.loads(r)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            resp = {}

        return resp
