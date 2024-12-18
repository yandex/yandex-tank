import collections
import time
import pytest

from yandextank.plugins.Autostop.cumulative_criterions import TotalNegativeNetCodesCriterion

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
