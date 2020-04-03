# coding: utf-8
"""
    yasmapi
    =======

    Итерфейс к компоненту yasmfront Голована. Подробнее об API yasmfront:
    https://wiki.yandex-team.ru/MaksimKlimin/YasmfrontAPI

    Данный модуль реализует запрос получения исторических и realtime данных.

    .. _example:

    Пример единичного получения данных
    ----------------------------------

    >>> from time import time
    >>> from yasmapi import GolovanRequest
    >>> host = "ASEARCH"
    >>> period = 300  # Пятиминутные данные
    >>> et = time() - period * 5  # Интересуют последние гарантированно агрегированные точки
    >>> st = et - period * 3  # Три последние точки
    >>> signals = [
    ...    "common_self:havg(cpu-us_hgram)"
    ... ]
    >>> for timestamp, values in GolovanRequest(host, period, st, et, signals):
    ...     print timestamp, values
    ...
    1412841600 {'common_self:havg(cpu-us_hgram)': 19.108171039779478}
    1412841900 {'common_self:havg(cpu-us_hgram)': 18.709824913928905}
    1412842200 {'common_self:havg(cpu-us_hgram)': 18.604999055358412}

    .. _example_rt:

    Получение realtime данных в бесконечном цикле
    ---------------------------------------------

    >>> from yasmapi import RtGolovanRequest
    >>> host = "ASEARCH"
    >>> tags = "common_self"
    >>> signals = ["havg(cpu-us_hgram)"]
    >>> for point in RtGolovanRequest({host: {tags: signals}}):
    ... print point.ts, point.values[host][tags]
    ...
    ...
    1463562035 {u'havg(cpu-us_hgram)': 24.490658256028667}
    1463562040 {u'havg(cpu-us_hgram)': 24.544982687419513}
    1463562045 {u'havg(cpu-us_hgram)': 24.588835890673014}
    1463562050 {u'havg(cpu-us_hgram)': 24.224413881684836}

    .. _periods:

    Периоды
    -------

    В Головане существуют несколько стандартных периодов:

        * 5 — Пятисекундные данные
        * 300 — Пятиминутные данные, расчитываются раз в 25 минут
        * 3600 — Часовые данные, расчитываются раз в час
        * 10800 — Трёхчасовые данные, расчитываются раз в три часа
        * 21600 — Шестичасовые данные, расчитываются раз в шесть часов
        * 43200 — Двенадцатичасовые данные, расчитываются раз в двенадцать часов
        * 86400 — Суточные данные, расчитываются раз в сутки

    Использование любых других периодов приведёт к отсутствию ответа. Не стоит запрашивать
    интервалы, правый край которых больше чем (now - время расчёта прериода), так как,
    вероятнее всего, этих данных ещё нет.

    .. _signals:

    Сигналы
    -------

    Сигналы для запросов к :class:`GolovanRequest` записываются в полностью квалифицированной форме, то есть: `<тег>:<модуль>-<сигнал>`,
    где тег может быть комбинацией из пяти тегов, например `mmeta_prestable_imgs-main_sas_yandsearch`,
    либо группой всех тегов одного типа инстанса, например `mmeta_self`, либо в формате динамиклов `itype=mmeta;ctype=prestable;prj=imgs-main;geo=sas`.

    Установка
    ---------

    Пакет распространяется через pypi.yandex-team.ru, таким образом, в простом
    варианте установка выглядит как::

        $ pip install -i https://pypi.yandex-team.ru/simple/ yasmapi

    либо можно определить репозиторий в файле `~/.pip/pip.conf`::

        [global]
        index-url = https://pypi.yandex-team.ru/simple/

    и устанавливать как обычно.

    Более подробно можно прочитать по ссылке https://wiki.yandex-team.ru/pypi
"""

from .core import (VERSION, USER_AGENT, USER_AGENT_PREFIX, HOSTNAME_HEADER, USERNAME_HEADER,
                   Transport, adjust_timestamp)
from .hist import GolovanRequest, RetryLimitExceeded, hist_request
from .rt import RtError, RtGolovanRequest, TsPoints
