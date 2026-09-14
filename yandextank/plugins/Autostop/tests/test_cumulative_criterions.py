import collections
import time
import pytest

from yandextank.plugins.Autostop.cumulative_criterions import (
    TotalFracTimeCriterion,
    TotalHTTPCodesCriterion,
    TotalHTTPTrendCriterion,
    TotalNegativeHTTPCodesCriterion,
    TotalNegativeNetCodesCriterion,
    TotalNetCodesCriterion,
)

WINDOW_SIZE = 10


def get_data(cnt_by_code):
    return {
        "overall": {"net_code": {"count": cnt_by_code}, "interval_real": {"len": sum(cnt_by_code.values())}},
        "ts": int(time.time()),
    }


def assert_notify_only_from_specified_sec(criterion, data, sec_start_notify):
    actual = []
    expected = []
    for sec_num in range(1, sec_start_notify * 3):
        expected_notified = sec_num >= sec_start_notify  # window's size
        expected.append(expected_notified)
        actually_notified = criterion.notify(data, stat=None)
        actual.append(actually_notified)
    assert all(exp == act for exp, act in zip(expected, actual)), f"{collections.Counter(actual)}"


@pytest.mark.parametrize('code', ['0', '1', '100'])
@pytest.mark.parametrize('not_matched_codes', ['1%', '50%', '100%', '1', '50', '100'])
def test_neg_net_code_notify_is_false_when_no_other_codes(code, not_matched_codes):
    criterion = TotalNegativeNetCodesCriterion(autostop=None, param_str=f"{code}, {not_matched_codes}, 10s")
    cnt_by_code = {code: 100}
    data = get_data(cnt_by_code)
    for sec_num in range(WINDOW_SIZE * 2):
        notification = criterion.notify(data, stat=None)
        assert not notification


@pytest.mark.parametrize('code', [0, 1, 100])
@pytest.mark.parametrize('not_matched_codes', ['1%', '50%', '100%', '1', '50', '100'])
def test_neg_net_code_notify_is_true_when_only_other_codes(code, not_matched_codes):
    criterion = TotalNegativeNetCodesCriterion(autostop=None, param_str=f"{code}, {not_matched_codes}, {WINDOW_SIZE}s")
    cnt_by_code = {str(code + 1): 100}
    data = get_data(cnt_by_code)
    assert_notify_only_from_specified_sec(criterion, data, WINDOW_SIZE)


@pytest.mark.parametrize('code', ['0', '1', '100'])
@pytest.mark.parametrize('non_matching_codes_percentage', [1, 50, 100])
def test_neg_net_code_notify_if_every_second_above_threshold(code, non_matching_codes_percentage):
    criterion = TotalNegativeNetCodesCriterion(
        autostop=None, param_str=f"{code}, {non_matching_codes_percentage}%, {WINDOW_SIZE}s"
    )
    total_requests = 1000
    non_matching_codes = non_matching_codes_percentage * total_requests / 100
    matching_codes = total_requests - non_matching_codes
    cnt_by_code = {code: matching_codes, "110": non_matching_codes}
    data = get_data(cnt_by_code)
    assert_notify_only_from_specified_sec(criterion, data, WINDOW_SIZE)


@pytest.mark.parametrize('code', ['0', '1', '100'])
@pytest.mark.parametrize('non_matching_codes_cnt', [1, 50, 100])
def test_neg_net_code_notify_is_false_when_no_data(code, non_matching_codes_cnt):
    criterion = TotalNegativeNetCodesCriterion(
        autostop=None, param_str=f"{code}, {non_matching_codes_cnt}, {WINDOW_SIZE}s"
    )
    data = get_data(cnt_by_code={})
    for sec_num in range(WINDOW_SIZE * 2):
        notification = criterion.notify(data, stat=None)
        assert not notification


def test_neg_net_code_notify_if_average_above_threshold():
    code = '0'
    other_code = '110'
    criterion = TotalNegativeNetCodesCriterion(autostop=None, param_str=f"{code}, 50, 10s")
    notification = False
    for _ in range(5):
        notification = criterion.notify(get_data({other_code: 40}), stat=None)
    for _ in range(5):
        notification = criterion.notify(get_data({other_code: 80}), stat=None)
    assert notification


# --- помощники для тестов ниже -----------------------------------------------

# Агрегатор отдаёт только непустые бины гистограммы, каждый — своей правой границей, в мкс.
FAST_BIN = 60_000  # ответы 50–60 мс
SLOW_BIN = 1_500_000  # ответы 1–1,5 с


def part(codes, length, rt_bin=FAST_BIN):
    # Одни и те же коды и в proto_code, и в net_code: отсчёт годится любому критерию.
    return {
        'interval_real': {'len': length, 'hist': {'data': [length], 'bins': [rt_bin]}},
        'proto_code': {'count': dict(codes)},
        'net_code': {'count': dict(codes)},
    }


def second(codes=None, length=None, rt_bin=FAST_BIN, tagged=None, ts=0):
    codes = codes or {}
    if length is None:
        length = sum(codes.values())
    return {'overall': part(codes, length, rt_bin), 'tagged': tagged or {}, 'ts': ts}


def fired_at(criterion, seconds):
    """Номер секунды (с единицы), на которой критерий впервые сработал, или None."""
    for number, sample in enumerate(seconds, start=1):
        if criterion.notify(sample, stat=None):
            return number
    return None


@pytest.mark.parametrize(
    'cls, param_str, type_string, rc',
    [
        (TotalFracTimeCriterion, '300ms, 70%, 3s', 'total_time', 25),
        (TotalHTTPCodesCriterion, '5xx, 10%, 3s', 'total_http', 26),
        (TotalNetCodesCriterion, '110, 10%, 3s', 'total_net', 27),
        (TotalNegativeHTTPCodesCriterion, '2xx, 10%, 3s', 'negative_http', 28),
        (TotalNegativeNetCodesCriterion, '0, 10%, 3s', 'negative_net', 29),
        (TotalHTTPTrendCriterion, '2xx, 3s', 'http_trend', 30),
    ],
)
def test_cumulative_criteria_config_name_and_exit_code(cls, param_str, type_string, rc):
    # Имя и код выхода — внешний контракт из docs/core_and_modules.rst: по коду CI различает причину остановки.
    assert cls.get_type_string() == type_string
    assert cls(autostop=None, param_str=param_str).get_rc() == rc


# --- total_time: доля медленных ответов за окно ------------------------------


def slow(length=10):
    return second(length=length, rt_bin=SLOW_BIN)


def fast(length=10):
    return second(length=length, rt_bin=FAST_BIN)


def test_total_time_fires_only_when_window_is_full():
    criterion = TotalFracTimeCriterion(autostop=None, param_str='300ms, 70%, 3s')

    assert fired_at(criterion, [slow()] * 10) == 3


def test_total_time_does_not_fire_on_fast_responses():
    criterion = TotalFracTimeCriterion(autostop=None, param_str='300ms, 70%, 3s')

    assert fired_at(criterion, [fast()] * 10) is None


@pytest.mark.parametrize('slow_count, expected', [(70, 2), (69, None)])
def test_total_time_ratio_is_weighted_by_responses_in_window(slow_count, expected):
    # Среднее долей по секундам дало бы 50% и не сработало бы: считается доля ответов всего окна.
    criterion = TotalFracTimeCriterion(autostop=None, param_str='300ms, 70%, 2s')

    assert fired_at(criterion, [fast(100 - slow_count), slow(slow_count)]) == expected


@pytest.mark.parametrize('slow_count, expected', [(50, 1), (49, None)])
def test_total_time_counts_only_bins_beyond_limit(slow_count, expected):
    # Бин с правой границей ровно на пороге целиком быстрый: медленные — только бины правее.
    criterion = TotalFracTimeCriterion(autostop=None, param_str='300ms, 50%, 1s')
    sample = second(length=100)
    sample['overall']['interval_real']['hist'] = {
        'data': [10, 90 - slow_count, slow_count],
        'bins': [100_000, 300_000, 1_000_000],
    }

    assert fired_at(criterion, [sample]) == expected


@pytest.mark.parametrize(
    'data, bins, expected',
    [([3, 7], [100_000, 1_500_000], 1), ([10], [300_000], None)],
    ids=['no-bin-at-limit', 'only-bin-at-limit'],
)
def test_total_time_slow_bins_do_not_depend_on_neighbour_bins(data, bins, expected):
    # Пустые бины агрегатор выкидывает, поэтому ближайший к лимиту непустой бин бывает любым.
    criterion = TotalFracTimeCriterion(autostop=None, param_str='300ms, 50%, 1s')
    sample = second(length=sum(data))
    sample['overall']['interval_real']['hist'] = {'data': data, 'bins': bins}

    assert fired_at(criterion, [sample]) == expected


def test_total_time_window_slides_past_old_fast_second():
    criterion = TotalFracTimeCriterion(autostop=None, param_str='300ms, 100%, 2s')

    assert fired_at(criterion, [fast(), slow(), slow()]) == 3


def test_total_time_cause_second_is_first_second_of_window():
    criterion = TotalFracTimeCriterion(autostop=None, param_str='300ms, 100%, 2s')
    seconds = [
        second(length=10, rt_bin=FAST_BIN, ts=1),
        second(length=10, rt_bin=SLOW_BIN, ts=2),
        second(length=10, rt_bin=SLOW_BIN, ts=3),
    ]

    assert fired_at(criterion, seconds) == 3
    assert criterion.cause_second[0]['ts'] == 2


@pytest.mark.parametrize(
    'tag_bin, overall_bin, expected',
    [(SLOW_BIN, FAST_BIN, 2), (FAST_BIN, SLOW_BIN, None)],
    ids=['slow-in-tag', 'slow-in-overall-only'],
)
def test_total_time_for_tag_uses_tag_histogram(tag_bin, overall_bin, expected):
    criterion = TotalFracTimeCriterion(autostop=None, param_str='300ms, 70%, 2s, mytag')
    sample = second(length=10, rt_bin=overall_bin, tagged={'mytag': part({}, 10, tag_bin)})

    assert fired_at(criterion, [sample] * 5) == expected


@pytest.mark.parametrize('with_tag_every', [None, 2], ids=['only-other-tags', 'tag-in-every-other-second'])
def test_total_time_ignores_seconds_without_tag(with_tag_every):
    # Секунда без тега не добавляет ответов ни в медленные, ни в общее число.
    criterion = TotalFracTimeCriterion(autostop=None, param_str='300ms, 100%, 2s, mytag')
    without_tag = second(length=100, rt_bin=FAST_BIN, tagged={'othertag': part({}, 100, FAST_BIN)})
    with_slow_tag = second(length=10, rt_bin=SLOW_BIN, tagged={'mytag': part({}, 10, SLOW_BIN)})
    seconds = [with_slow_tag if with_tag_every and n % with_tag_every else without_tag for n in range(1, 6)]

    assert fired_at(criterion, seconds) == (2 if with_tag_every else None)


@pytest.mark.parametrize(
    'param_str, rt_limit_us, ratio, window, tag',
    [
        ('300ms, 70%, 3s', 300_000, 0.7, 3, None),
        ('2s, 5%, 1m, mytag', 2_000_000, 0.05, 60, 'mytag'),
    ],
)
def test_total_time_parses_params(param_str, rt_limit_us, ratio, window, tag):
    criterion = TotalFracTimeCriterion(autostop=None, param_str=param_str)

    assert criterion.rt_limit == rt_limit_us
    assert criterion.fail_ratio_limit == pytest.approx(ratio)
    assert criterion.window_size == window
    assert criterion.tag == tag


@pytest.mark.parametrize(
    'param_str', ['300ms, 70%', '300ms, many%, 3s', '300ms, 70%, 3x', '300ms, 70, 3s', '300ms, 70%, 500ms']
)
def test_total_time_rejects_broken_params(param_str):
    # Опечатка обязана валить создание, а не давать критерий, который молча ничего не охраняет.
    with pytest.raises((IndexError, ValueError)):
        TotalFracTimeCriterion(autostop=None, param_str=param_str)


# --- total_http, total_net, negative_http, negative_net ----------------------

CODE_CLASSES = [
    TotalHTTPCodesCriterion,
    TotalNetCodesCriterion,
    TotalNegativeHTTPCodesCriterion,
    TotalNegativeNetCodesCriterion,
]

# Маска, «хороший» и «плохой» код; плохой — тот, что копит счётчик. У negative_* это код НЕ под маску.
CODE_CRITERIA = [
    pytest.param(TotalHTTPCodesCriterion, '5xx', '200', '500', id='total_http'),
    pytest.param(TotalNetCodesCriterion, '110', '0', '110', id='total_net'),
    pytest.param(TotalNegativeHTTPCodesCriterion, '2xx', '200', '500', id='negative_http'),
    pytest.param(TotalNegativeNetCodesCriterion, '0', '0', '110', id='negative_net'),
]


def codes_second(ok, bad, ok_count, bad_count, ts=0):
    return second({ok: ok_count, bad: bad_count}, ts=ts)


@pytest.mark.parametrize('cls, mask, ok, bad', CODE_CRITERIA)
@pytest.mark.parametrize('level, expected', [(10, 5), (11, None)])
def test_codes_absolute_level_is_sum_over_window(cls, mask, ok, bad, level, expected):
    # Абсолютный порог — сумма за окно, а не за секунду: по 2 плохих в секунду за 5 с дают 10.
    criterion = cls(autostop=None, param_str=f'{mask}, {level}, 5s')

    assert fired_at(criterion, [codes_second(ok, bad, 8, 2)] * 10) == expected


@pytest.mark.parametrize('cls, mask, ok, bad', CODE_CRITERIA)
def test_codes_criterion_waits_for_full_window(cls, mask, ok, bad):
    criterion = cls(autostop=None, param_str=f'{mask}, 1, 3s')

    assert fired_at(criterion, [codes_second(ok, bad, 0, 100)] * 10) == 3


@pytest.mark.parametrize('cls, mask, ok, bad', CODE_CRITERIA)
@pytest.mark.parametrize('bad_count, expected', [(10, 2), (9, None)])
def test_codes_relative_level_reached_exactly_fires(cls, mask, ok, bad, bad_count, expected):
    criterion = cls(autostop=None, param_str=f'{mask}, 10%, 2s')

    assert fired_at(criterion, [codes_second(ok, bad, 100 - bad_count, bad_count)] * 5) == expected


@pytest.mark.parametrize('cls, mask, ok, bad', CODE_CRITERIA)
@pytest.mark.parametrize('percent', [29, 44, 45, 57, 58])
def test_codes_relative_level_boundary_is_exact(cls, mask, ok, bad, percent):
    # Во float 29 / 100 * 100 == 28.999999999999996, и ровно 29% не дотягивало до порога 29%.
    criterion = cls(autostop=None, param_str=f'{mask}, {percent}%, 1s')

    assert fired_at(criterion, [codes_second(ok, bad, 100 - percent, percent)]) == 1


@pytest.mark.parametrize('cls, mask, ok, bad', CODE_CRITERIA)
@pytest.mark.parametrize(
    'counts, expected',
    [([(1000, 0), (0, 10)], None), ([(100, 900), (10, 0)], 2)],
    ids=['bad-in-quiet-second', 'bad-in-busy-second'],
)
def test_codes_relative_level_is_share_of_window_responses(cls, mask, ok, bad, counts, expected):
    # Среднее процентов по секундам дало бы 50% и 45%: секунда с десятком ответов весила как секунда с тысячей.
    criterion = cls(autostop=None, param_str=f'{mask}, 50%, 2s')

    assert fired_at(criterion, [codes_second(ok, bad, *c) for c in counts]) == expected


@pytest.mark.parametrize('cls, mask, ok, bad', CODE_CRITERIA)
def test_codes_mask_tolerates_space_before_comma(cls, mask, ok, bad):
    sample = codes_second(ok, bad, 5, 5)

    assert fired_at(cls(autostop=None, param_str=f'{mask} , 5, 1s'), [sample]) == 1
    assert fired_at(cls(autostop=None, param_str=f'{mask} , 6, 1s'), [sample]) is None


@pytest.mark.parametrize('cls, mask, ok, bad', CODE_CRITERIA)
def test_codes_window_forgets_old_seconds(cls, mask, ok, bad):
    # За всю стрельбу плохих 20 при пороге 10, но в любое окно 3 с попадает не больше 5.
    criterion = cls(autostop=None, param_str=f'{mask}, 10, 3s')
    burst = codes_second(ok, bad, 0, 5)
    calm = codes_second(ok, bad, 5, 0)

    assert fired_at(criterion, [burst, calm, calm] * 4) is None


@pytest.mark.parametrize('cls, mask, ok, bad', CODE_CRITERIA)
def test_codes_cause_second_is_first_second_of_window(cls, mask, ok, bad):
    # По причинной секунде плагин считает rps, на котором сломалась цель.
    criterion = cls(autostop=None, param_str=f'{mask}, 100%, 2s')
    seconds = [
        codes_second(ok, bad, 10, 0, ts=1),
        codes_second(ok, bad, 0, 10, ts=2),
        codes_second(ok, bad, 0, 10, ts=3),
    ]

    assert fired_at(criterion, seconds) == 3
    assert criterion.cause_second[0]['ts'] == 2


@pytest.mark.parametrize('cls, mask, ok, bad', CODE_CRITERIA)
@pytest.mark.parametrize('bad_in_tag, expected', [(True, 2), (False, None)], ids=['bad-in-tag', 'bad-in-overall-only'])
def test_codes_for_tag_count_only_tag_codes(cls, mask, ok, bad, bad_in_tag, expected):
    criterion = cls(autostop=None, param_str=f'{mask}, 50%, 2s, mytag')
    good, broken = {ok: 10}, {bad: 10}
    tag_codes, overall_codes = (broken, good) if bad_in_tag else (good, broken)
    sample = second(overall_codes, tagged={'mytag': part(tag_codes, 10)})

    assert fired_at(criterion, [sample] * 5) == expected


@pytest.mark.parametrize('cls, mask, ok, bad', CODE_CRITERIA)
@pytest.mark.parametrize('level', ['1', '1%'])
def test_codes_ignore_seconds_without_tag(cls, mask, ok, bad, level):
    # Ответы чужих тегов не считаются ответами нужного тега, в том числе «не под маску» у negative_*.
    criterion = cls(autostop=None, param_str=f'{mask}, {level}, 2s, mytag')
    sample = second({bad: 10}, tagged={'othertag': part({bad: 10}, 10)})

    assert fired_at(criterion, [sample] * 5) is None


@pytest.mark.parametrize('cls, mask, ok, bad', CODE_CRITERIA[:2])
def test_positive_codes_share_is_not_diluted_by_seconds_without_tag(cls, mask, ok, bad):
    # Секунда без тега не добавляет в знаменатель ответы чужих тегов: 10 плохих из 10 ответов тега — 100%.
    criterion = cls(autostop=None, param_str=f'{mask}, 50%, 2s, mytag')
    with_tag = second({bad: 10}, tagged={'mytag': part({bad: 10}, 10)})
    without_tag = second({ok: 1000}, tagged={'othertag': part({ok: 1000}, 1000)})

    assert fired_at(criterion, [with_tag, without_tag]) == 2


@pytest.mark.parametrize('mask, matched', [('5xx', 7), ('50x', 5), ('503', 2), ('5XX', 7)])
def test_total_http_mask_counts_only_matching_codes(mask, matched):
    sample = second({'500': 3, '503': 2, '524': 2, '404': 4, '200': 10})
    at_level = TotalHTTPCodesCriterion(autostop=None, param_str=f'{mask}, {matched}, 1s')
    above_level = TotalHTTPCodesCriterion(autostop=None, param_str=f'{mask}, {matched + 1}, 1s')

    assert at_level.notify(sample, stat=None) is True
    assert above_level.notify(sample, stat=None) is False


@pytest.mark.parametrize('param_str', ['0, 1, 1s', '0, 1, 1s, mytag'])
def test_total_net_never_counts_success_code_zero(param_str):
    # Нулевой net-код — успех: даже маска, под которую он подходит, не делает его ошибкой.
    criterion = TotalNetCodesCriterion(autostop=None, param_str=param_str)
    sample = second({'0': 10}, tagged={'mytag': part({'0': 10}, 10)})

    assert fired_at(criterion, [sample] * 3) is None


@pytest.mark.parametrize('cls', CODE_CLASSES)
@pytest.mark.parametrize(
    'param_str, mask, level, is_relative, seconds, tag',
    [
        ('5XX, 10%, 10s', '5xx', 10.0, True, 10, None),
        ('5xx, 0.5%, 1m, mytag', '5xx', 0.5, True, 60, 'mytag'),
        ('5xx, 25, 2s', '5xx', 25, False, 2, None),
    ],
)
def test_codes_criteria_parse_params(cls, param_str, mask, level, is_relative, seconds, tag):
    criterion = cls(autostop=None, param_str=param_str)

    assert criterion.codes_mask == mask
    assert criterion.level == level
    assert criterion.is_relative is is_relative
    assert criterion.seconds_limit == seconds
    assert criterion.tag == tag


@pytest.mark.parametrize('cls', CODE_CLASSES)
@pytest.mark.parametrize(
    'param_str', ['5xx, 10%', '5xx, 1.5, 10s', '5xx, often, 10s', '5xx, 10%, 10x', '5xx, 10%, 500ms']
)
def test_codes_criteria_reject_broken_params(cls, param_str):
    # Абсолютный порог — целое число ответов: дробный — ошибка конфига, а не округление.
    with pytest.raises((IndexError, ValueError)):
        cls(autostop=None, param_str=param_str)


# --- http_trend: падение числа ответов с кодами под маску --------------------


def test_http_trend_fires_on_steady_decline():
    # Тренд — по разностям соседних секунд, поэтому окну 3 с нужно четыре отсчёта.
    criterion = TotalHTTPTrendCriterion(autostop=None, param_str='2xx, 3s')
    seconds = [second({'200': n, '500': 100 - n}) for n in (100, 96, 92, 88, 84)]

    assert fired_at(criterion, seconds) == 4


@pytest.mark.parametrize(
    'seconds',
    [
        [second({'200': 100})] * 6,
        [second({'200': n}) for n in (50, 60, 70, 80, 90, 100)],
        [second({'200': 50, '500': n}) for n in (50, 40, 30, 20, 10, 0)],
    ],
    ids=['flat', 'rising', 'only-other-codes-drop'],
)
def test_http_trend_does_not_fire_without_decline(seconds):
    criterion = TotalHTTPTrendCriterion(autostop=None, param_str='2xx, 3s')

    assert fired_at(criterion, seconds) is None


def test_http_trend_noise_within_measurement_error_does_not_fire():
    # Среднее падение −4 в секунду при погрешности 6 — шум, а не тренд.
    criterion = TotalHTTPTrendCriterion(autostop=None, param_str='2xx, 3s')
    seconds = [second({'200': n}) for n in (100, 90, 98, 88)]

    assert fired_at(criterion, seconds) is None


@pytest.mark.parametrize(
    'tag_counts, overall_counts, expected',
    [((100, 96, 92, 88), (300, 310, 320, 330), 4), ((100, 100, 100, 100), (300, 250, 200, 150), None)],
    ids=['tag-declines', 'overall-declines'],
)
def test_http_trend_for_tag_follows_tag_codes(tag_counts, overall_counts, expected):
    criterion = TotalHTTPTrendCriterion(autostop=None, param_str='2xx, 3s, mytag')
    seconds = [
        second({'200': total}, tagged={'mytag': part({'200': in_tag}, in_tag)})
        for in_tag, total in zip(tag_counts, overall_counts)
    ]

    assert fired_at(criterion, seconds) == expected


@pytest.mark.parametrize(
    'param_str, mask, seconds, tag',
    [('2xx, 10s', '2xx', 10, None), ('2XX, 1m, mytag', '2xx', 60, 'mytag'), ('2xx , 10s', '2xx', 10, None)],
)
def test_http_trend_parses_params(param_str, mask, seconds, tag):
    criterion = TotalHTTPTrendCriterion(autostop=None, param_str=param_str)

    assert criterion.codes_mask == mask
    assert criterion.seconds_limit == seconds
    assert criterion.tag == tag


@pytest.mark.parametrize('param_str', ['2xx', '2xx, 10x', '2xx, 500ms'])
def test_http_trend_rejects_broken_params(param_str):
    with pytest.raises((IndexError, ValueError)):
        TotalHTTPTrendCriterion(autostop=None, param_str=param_str)
