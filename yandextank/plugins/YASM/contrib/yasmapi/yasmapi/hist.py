# coding: utf-8

import time
import logging

from .core import VERSION, Transport


__all__ = ["GolovanRequest", "RetryLimitExceeded", "hist_request"]

USER_AGENT = "yasmapi/".format(VERSION)

logging.basicConfig()
log = logging.getLogger('yasmapi')
log.setLevel(logging.INFO)


def adjust_timestamp(ts, period):
    return int(ts - (ts % period))


def hist_request(host, period, req_id, st, et, fields):
    """
    Функция формирует hist запрос в yasmfront.

    :param str host: Хост либо группа, по которой запрашивются данные
    :param int period: Период интересующих данных, смотри :ref:`periods`
    :param req_id: Идентификатор запроса.
    :param int st: Начало временного отрезка по которому производится запрос
    :param int et: Конец временного отрезка по которому производится запрос
    :param [str] fields: Список строк с сигналами, смотри :ref:`signals`
    """

    st = adjust_timestamp(st, period)
    et = adjust_timestamp(et, period)

    return {
        "name": "hist",
        "id": req_id,
        "host": host,
        "st": st,
        "et": et,
        "period": period,
        "signals": fields,
    }


def group_request(st, et, load_segments, period):
    st = int(st)
    et = int(et)
    et = min(int(time.time()), et)

    while True:

        next = st + load_segments * period

        rq = (st, min(next, et))
        yield rq

        st = next

        if next > et:
            break


class RetryLimitExceeded(Exception):
    """
    Ответ на каждую попытку запроса или перезапроса данных содержал ошибки.
    """
    pass


class GolovanRequest(object):
    """
    Класс реализует интерфейс для запроса исторических данных из yasmfront.
    Инстанс класса является итератором итерирующим `(timestamp, {signal: value})`.
    Смотри :ref:`example`.

    :param str host: Хост либо группа, по которой запрашивются данные
    :param int period: Период интересующих данных, смотри :ref:`periods`
    :param int st: Начало временного отрезка по которому производится запрос
    :param int et: Конец временного отрезка по которому производится запрос
    :param [str] fields: Список строк с сигналами, смотри :ref:`signals`
    :param int load_segments: Количество записей загружаемых за раз
    :param int|float load_delay: Задержка между загрузками
    :param int max_retry: Максимальное количество попыток перезагрузки данных при ошибочном ответе
    :param int|float retry_delay: Задержка между загрузками ошибочных данных, в секундах
    :param bool explicit_fail: Упасть с ошибкой :class:`RetryLimitExceeded`, если во всех запросах
                               были ошибки.
    :param Transport transport: Транспорт для общения с yasmfront. Выбирая кастомный транспорт
                                можно изменить хост, таймаут. Потенциально можно изменить
                                протокол общения.
    """

    GOLOVAN_PATH = "hist/data"

    def __init__(self, host, period, st, et, fields=None, load_segments=300, load_delay=0,
                 max_retry=5, retry_delay=0.1, explicit_fail=False, transport=None):
        self.host = host
        self.period = period

        self.st = adjust_timestamp(st, period)
        self.et = adjust_timestamp(et, period)
        self.fields = fields or []

        self.load_segments = load_segments
        self.load_delay = load_delay

        self.max_retry = max_retry
        self.retry_delay = retry_delay
        self.explicit_fail = explicit_fail
        self.transport = transport or Transport()

    def _extract_response_data(self, response, expected_req_id):
        ctx = response.get("response", {}).get(expected_req_id, {})
        return ctx.get("content", {})

    def _request(self, request):
        resp = None

        for _ in range(max(1, self.max_retry + 1)):
            resp = self.transport.request(request, self.GOLOVAN_PATH)
            if resp.get("response", {}).get("errors"):
                log.error('Got error %s', resp['response']['errors'])
                time.sleep(self.retry_delay)
            else:
                break
        else:
            if self.explicit_fail:
                raise RetryLimitExceeded("Max retry limit exceeded.")
        return resp

    def __iter__(self):
        fields = self.fields
        last_ts = 0

        for st, et in group_request(self.st, self.et, self.load_segments, self.period):
            req_id = "{0}:{1}_{2}_{3}".format(self.host, st, et, self.period)
            response_data = self._extract_response_data(
                self._request({"ctxList": [hist_request(self.host, self.period, req_id,
                                           st, et, fields)]}),
                req_id
            )

            response_timeline = response_data.get("timeline", [])
            response_values = response_data.get("values", {})

            response_len = len(response_timeline)

            if not fields:
                fields = response_values.keys()
            else:
                for field_name in fields:
                    if field_name not in response_values:
                        response_values[field_name] = [None] * response_len
            for idx in xrange(0, response_len):
                record_ts = response_timeline[idx]
                if record_ts <= last_ts or record_ts > self.et:  # skip overlapping
                    continue
                record_values = {}
                for field_name in fields:
                    # XXX: looks strange, `{}.get()[idx]` leads to `None[idx]` dereference
                    record_values[field_name] = response_values.get(field_name)[idx]
                last_ts = record_ts
                yield record_ts, record_values

            if self.load_delay:
                time.sleep(self.load_delay)
