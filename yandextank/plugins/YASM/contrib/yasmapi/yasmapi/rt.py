# coding: utf-8

import time
from collections import namedtuple, defaultdict

from .core import Transport


class RtError(Exception):
    "Запрос для :class:`RtGolovanRequest` сформирован не правильно, или в процессе запроса к rtfront'у произошла ошибка"


class TsPoints(namedtuple("TsPoints", "ts values errors")):
    """Данные по одной realtime точке

    :param float ts: Timestamp точки
    :param dict values: значения по конкретным сигналам `{"host": {"tags": {"signal": val}}}`
    :param dict errors: известные ошибки, выявленные при вычислении сигналов в данной точке ({"signal": ["error"]})
    """

OLD_FORMAT_TIMELINE = "timeline"


def is_old_format(response):
    return OLD_FORMAT_TIMELINE in response


def _new_point_data(points, time_index):
    point = points[time_index]
    return point["value"], point.get("errors")


def _get_latest_ts(response):
    if is_old_format(response):
        return response[OLD_FORMAT_TIMELINE][0]
    else:
        return min(ts[0]["timestamp"] for ts in response.itervalues())


def split_host_tags_signal(hts):
    key_tokens = hts.split(":")
    if len(key_tokens) != 3:
        raise RtError("Strange rtfront response: {}".format(hts))
    return key_tokens


class RtGolovanRequest(object):
    """
    Класс реализует интерфейс для запроса realtime данных из rtfront.
    Инстанс класса является итератором по объектам :class:`TsPoints`.
    Смотри :ref:`example_rt`.

    :param dict request_data: Запрашиваемыве сигналы должны быть в формате `{'host': {'tags': ['signal']}}`
    :param Transport transport: Транспорт для общения с yasmfront. Выбирая кастомный транспорт
                                можно изменить хост, таймаут. Потенциально можно изменить
                                протокол общения.
    """

    REQUEST_INTERVAL = 5
    GOLOVAN_PATH = "rt"

    def __init__(self, request_data, transport=None):
        if not isinstance(request_data, dict):
            raise RtError("'request_data' must have {'host': {'tag': ['signal']}} format")
        self.request_data = request_data
        self._processed_points = set()
        self.transport = transport or Transport()

    def request(self, request=None):
        """Сделать  один запрос к tfront'у
        See https://wiki.yandex-team.ru/jandekspoisk/sepe/golovan/rtfront/http/#rt2 for details

        :param dict request: тело запроса (python структура)
        """
        if request is None:
            request = {"signals": ["%s:%s:%s" % (host, tags, signal)
                                   for host, tags_signals in self.request_data.iteritems()
                                   for tags, signals in tags_signals.iteritems()
                                   for signal in signals]}
        return self.transport.request(request, self.GOLOVAN_PATH)

    def _process_rt(self, response):
        if is_old_format(response):
            return self._old_format_process_rt(response)
        else:
            return self._new_format_process_rt(response)

    def _new_format_process_rt(self, response):
        """ format example:
        {
            "ASEARCH:base_self:loadlog-success": [
                {
                    "timestamp": 1360410500,
                    "value": 26344397,
                    "errors": [
                        "missing values for MAN1.0"
                    ]
                },
                ...
            ],
            ...
        }
        """
        any_signal_key, any_signal_times = next(response.iteritems())
        for time_index, one_ts_data in enumerate(any_signal_times):
            ts = one_ts_data["timestamp"]
            if ts in self._processed_points:
                continue
            result_values = defaultdict(lambda: defaultdict(dict))
            result_errors = defaultdict(lambda: defaultdict(dict))
            for key, signal_info in response.iteritems():
                host, tags, signal = split_host_tags_signal(key)
                value, errors = _new_point_data(signal_info, time_index)
                if value is not None:
                    result_values[host][tags][signal] = value
                if errors:
                    result_errors[host][tags][signal] = errors
            if result_values:
                yield TsPoints(ts, result_values, result_errors)

    def _old_format_process_rt(self, response):
        """ format example:
        {
            "timeline": [1360410500, 1360410505],
            "values": {
                "host1:tag_self:module-signal1": [1, 2],
                "host2:tag_self:module-signal1": [3, 4]
            },
            "messages": [[], ["missing values for MAN1.0"]]
        }
        """
        timeline = response[OLD_FORMAT_TIMELINE]
        errors = response["messages"]
        host_tag_signals_values = response["values"]
        for index in xrange(len(timeline)):
            ts = timeline[index]
            if ts in self._processed_points:
                continue
            ts_errors = errors[index] or {}
            result_values = defaultdict(lambda: defaultdict(dict))
            result_errors = defaultdict(lambda: defaultdict(dict))
            for host_tags_signal, signal_values in host_tag_signals_values.iteritems():
                host, tags, signal = split_host_tags_signal(host_tags_signal)
                value = signal_values[index]
                if value is not None:
                    result_values[host][tags][signal] = value
                if ts_errors:
                    result_errors[host][tags][signal] = ts_errors[:]
            if result_values:
                yield TsPoints(ts, result_values, result_errors)

    def points_from_request(self):
        """Do single request and extract all new points from it."""
        response_with_status = self.request()
        if response_with_status["status"] != "ok":
            raise RtError(response_with_status)
        response = response_with_status["response"]
        latest_ts = _get_latest_ts(response)
        for new_point in self._process_rt(response):
            self._processed_points.add(new_point.ts)
            yield new_point

        self._processed_points = {ts for ts in self._processed_points
                                  if ts >= latest_ts}

    def __iter__(self, interval=None):
        """Generate realtime points in infinite loop
        Args:
            interval float: sleep time between request to rtfront. Default: 5
        """
        while True:
            for point in self.points_from_request():
                yield point
            time.sleep(interval or self.REQUEST_INTERVAL)
