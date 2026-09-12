"""Тесты мгновенных критериев автостопа.

Критерии решают, оборвать ли стрельбу и с каким кодом. Ошибка здесь не падает:
либо прогон дожигает нагрузку, которую надо было остановить, либо режется на
первой секунде, и в CI уезжает красный вердикт по здоровой цели. Поэтому здесь
проверяется не «работает ли», а на КАКОЙ секунде срабатывает и что сбрасывает
счётчик.
"""

import pytest

from yandextank.plugins.Autostop.criterions import (
    AvgTimeCriterion,
    HTTPCodesCriterion,
    NetCodesCriterion,
    QuantileCriterion,
    TimeLimitCriterion,
    UsedInstancesCriterion,
)


class FakeAutostop:
    """Счётчик обращений вместо плагина: критерий обязан регистрироваться на каждой плохой секунде."""

    def __init__(self):
        self.counted = []

    def add_counting(self, criterion):
        self.counted.append(criterion)


def data(length=0, rt_total=0, proto=None, net=None, quantiles=None, tagged=None):
    """Один отсчёт агрегатора. interval_real.total в микросекундах, как в phout."""
    overall = {
        'interval_real': {'len': length, 'total': rt_total},
        'proto_code': {'count': proto or {}},
        'net_code': {'count': net or {}},
    }
    if quantiles is not None:
        overall['interval_real']['q'] = {'q': list(quantiles.keys()), 'value': list(quantiles.values())}
    return {'overall': overall, 'tagged': tagged or {}, 'ts': 0}


def feed(criterion, sample, times):
    """Возвращает номер секунды (с единицы), на которой критерий сработал, или None."""
    for second in range(1, times + 1):
        if criterion.notify(sample, stat={'metrics': {'instances': 0}}):
            return second
    return None


# --- средняя длительность ответа ---------------------------------------------


def test_avg_time_fires_exactly_on_limit_second():
    # 200 мс при лимите 100 мс: нарушение каждую секунду, порог — три секунды.
    criterion = AvgTimeCriterion(FakeAutostop(), '100ms, 3s')

    assert feed(criterion, data(length=1, rt_total=200_000), times=10) == 3


def test_avg_time_resets_counter_on_good_second():
    """Две плохие секунды, затем хорошая — счётчик обнуляется, и до порога снова три плохих."""
    autostop = FakeAutostop()
    criterion = AvgTimeCriterion(autostop, '100ms, 3s')
    bad = data(length=1, rt_total=200_000)
    good = data(length=1, rt_total=10_000)

    assert criterion.notify(bad, None) is False
    assert criterion.notify(bad, None) is False
    assert criterion.notify(good, None) is False
    assert criterion.seconds_count == 0, 'хорошая секунда обязана обнулить счётчик'
    assert feed(criterion, bad, times=3) == 3
    assert len(autostop.counted) == 5, 'каждая плохая секунда регистрируется в автостопе'


def test_avg_time_keeps_first_bad_second_as_cause():
    """Причина остановки — ПЕРВАЯ плохая секунда, а не последняя: по ней потом объясняют обрыв."""
    criterion = AvgTimeCriterion(FakeAutostop(), '100ms, 3s')
    first = data(length=1, rt_total=200_000)
    second = data(length=2, rt_total=600_000)

    criterion.notify(first, None)
    criterion.notify(second, None)

    assert criterion.cause_second[0] is first


def test_avg_time_survives_second_without_requests():
    """Секунда без запросов — штатная ситуация (пауза в схеме, прогрев), а не повод падать.

    До LOAD-3696 здесь было деление на ноль, и исключение уносило поток автостопа:
    стрельба продолжалась вообще без контроля критериев.
    """
    criterion = AvgTimeCriterion(FakeAutostop(), '100ms, 3s')

    assert criterion.notify(data(length=0, rt_total=0), None) is False
    assert criterion.seconds_count == 0


def test_avg_time_ignores_other_tags():
    criterion = AvgTimeCriterion(FakeAutostop(), '100ms, 2s, mytag')
    other = data(length=1, rt_total=900_000, tagged={'othertag': {'interval_real': {'len': 1, 'total': 900_000}}})

    assert feed(criterion, other, times=5) is None


def test_avg_time_rc_is_time():
    assert AvgTimeCriterion(FakeAutostop(), '100ms, 1s').get_rc() == AvgTimeCriterion.RC_TIME


# --- коды протокола ----------------------------------------------------------


def test_http_mask_matches_only_its_family():
    criterion = HTTPCodesCriterion(FakeAutostop(), '5xx, 1, 1s')
    fives = data(length=10, proto={'500': 1, '200': 9})
    twos = data(length=10, proto={'200': 10})

    assert criterion.notify(fives, None) is True
    criterion.seconds_count = 0
    assert criterion.notify(twos, None) is False


def test_http_relative_level_counts_share_not_count():
    """10% при 5 ошибках из 100 — не срабатывает, при 15 — срабатывает."""
    criterion = HTTPCodesCriterion(FakeAutostop(), '5xx, 10%, 1s')

    assert criterion.notify(data(length=100, proto={'503': 5, '200': 95}), None) is False
    assert criterion.notify(data(length=100, proto={'503': 15, '200': 85}), None) is True


def test_http_relative_level_on_empty_second_does_not_fire():
    """Ни одного ответа за секунду — доля не считается делением на ноль и не превращается в 100%."""
    criterion = HTTPCodesCriterion(FakeAutostop(), '5xx, 10%, 1s')

    assert criterion.notify(data(length=0, proto={}), None) is False


def test_http_absolute_level_fires_on_limit_second():
    criterion = HTTPCodesCriterion(FakeAutostop(), '5xx, 3, 2s')
    sample = data(length=10, proto={'500': 3})

    assert feed(criterion, sample, times=5) == 2


def test_http_rc_is_http():
    assert HTTPCodesCriterion(FakeAutostop(), '5xx, 1, 1s').get_rc() == HTTPCodesCriterion.RC_HTTP


# --- сетевые коды ------------------------------------------------------------


def test_net_criterion_excludes_success_code_zero():
    """Нулевой net-код — это успех, и в счёт ошибок он попадать не должен."""
    criterion = NetCodesCriterion(FakeAutostop(), '0, 1, 1s')

    assert criterion.notify(data(length=10, net={'0': 10}), None) is False


def test_net_criterion_excludes_success_code_zero_given_as_int():
    """Тот же ноль, пришедший целым ключом.

    Агрегатор отдаёт коды и строками, и числами (count_matched_codes принимает оба),
    а отбрасывался только строковый '0' — целый ноль считался ошибкой и мог оборвать
    здоровую стрельбу (LOAD-3696).
    """
    criterion = NetCodesCriterion(FakeAutostop(), '0, 1, 1s')

    assert criterion.notify(data(length=10, net={0: 10}), None) is False


def test_net_criterion_fires_on_real_error_code():
    criterion = NetCodesCriterion(FakeAutostop(), '110, 1, 1s')

    assert criterion.notify(data(length=10, net={'110': 1, '0': 9}), None) is True


def test_net_rc_is_net():
    assert NetCodesCriterion(FakeAutostop(), '110, 1, 1s').get_rc() == NetCodesCriterion.RC_NET


# --- квантили ----------------------------------------------------------------


def test_quantile_fires_when_over_limit():
    criterion = QuantileCriterion(FakeAutostop(), '99.0, 100ms, 2s')
    # значения квантилей в микросекундах
    sample = data(length=10, quantiles={99.0: 200_000})

    assert feed(criterion, sample, times=5) == 2


def test_quantile_does_not_fire_below_limit():
    criterion = QuantileCriterion(FakeAutostop(), '99.0, 100ms, 1s')

    assert criterion.notify(data(length=10, quantiles={99.0: 50_000}), None) is False


def test_quantile_missing_in_data_does_not_fire():
    """Запрошенной квантили нет в отсчёте — критерий молчит и только пишет предупреждение.

    Это осознанно оставленное поведение (fail-open): отсутствие данных не повод рвать
    стрельбу. Тест держит его явным, чтобы «починка» не превратила молчание в обрыв.
    """
    criterion = QuantileCriterion(FakeAutostop(), '99.0, 100ms, 1s')

    assert criterion.notify(data(length=10, quantiles={95.0: 900_000}), None) is False


def test_quantile_for_tag_uses_its_own_quantile_keys():
    """Ключи квантилей берутся из того же набора, откуда значения.

    До LOAD-3696 значения брались из тега, а перечень квантилей — из overall, и при
    разных наборах zip сдвигал значения: критерий на 99-ю квантиль сравнивал чужое
    число (LOAD-3696).
    """
    criterion = QuantileCriterion(FakeAutostop(), '99.0, 100ms, 1s')
    sample = data(
        length=10,
        quantiles={50.0: 10_000, 99.0: 20_000},
        tagged={'mytag': {'interval_real': {'len': 10, 'q': {'q': [99.0], 'value': [500_000]}}}},
    )
    criterion.tag = 'mytag'

    assert criterion.notify(sample, None) is True, 'превышение по тегу обязано сработать'


# --- лимит времени ----------------------------------------------------------


def test_time_limit_fires_after_limit(monkeypatch):
    clock = {'now': 1000.0}
    monkeypatch.setattr('yandextank.plugins.Autostop.criterions.time.time', lambda: clock['now'])
    criterion = TimeLimitCriterion(FakeAutostop(), '10s')

    clock['now'] = 1009.0
    assert criterion.notify(data(), None) is False
    clock['now'] = 1011.0
    assert criterion.notify(data(), None) is True


# --- использованные инстансы -------------------------------------------------


class FakePandora:
    """Минимальный плагин-генератор: критерию нужен только его config_contents."""

    def __init__(self, times):
        self.config_contents = {'pools': [{'startup': {'type': 'once', 'times': times}}]}


class FakeCore:
    def __init__(self, options, pandora=None):
        self.options = options
        self.pandora = pandora

    def get_option(self, section, option, default=None):
        return self.options.get((section, option), default)

    def get_plugin_of_type(self, plugin_type):
        assert self.pandora is not None, 'плагин в этом тесте не подставлен'
        return self.pandora


def instances_criterion(param_str, options, pandora=None):
    autostop = FakeAutostop()
    autostop.core = FakeCore(options, pandora)
    return UsedInstancesCriterion(autostop, param_str)


PANDORA_ON = {('pandora', 'enabled'): True, ('phantom', 'enabled'): False}


def test_instances_absolute_level_fires():
    criterion = instances_criterion('5, 2s', PANDORA_ON, FakePandora(times=100))
    fired = None
    for second in range(1, 5):
        if criterion.notify(data(), stat={'metrics': {'instances': 7}}):
            fired = second
            break
    assert fired == 2


def test_instances_relative_level_uses_generator_limit():
    """50% считается от лимита инстансов генератора, а не от абсолютного числа."""
    criterion = instances_criterion('50%, 1s', PANDORA_ON, FakePandora(times=100))

    assert criterion.notify(data(), stat={'metrics': {'instances': 40}}) is False
    assert criterion.notify(data(), stat={'metrics': {'instances': 60}}) is True


def test_instances_criterion_refuses_startup_other_than_once():
    """Схема не 'once' — лимит инстансов неизвестен, и критерий обязан отказаться, а не считать от нуля."""
    pandora = FakePandora(times=10)
    pandora.config_contents = {'pools': [{'startup': {'type': 'const', 'times': 10}}]}

    with pytest.raises(ValueError):
        instances_criterion('50%, 1s', PANDORA_ON, pandora)


def test_instances_criterion_refuses_without_load_generator():
    """Без включённого phantom или pandora критерий создать нельзя — иначе он молча ничего не охраняет."""
    with pytest.raises(ValueError):
        instances_criterion('50%, 2s', {})
