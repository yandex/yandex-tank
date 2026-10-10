import pytest

from yandextank.plugins.Autostop.criterions import AvgTimeCriterion


def get_data(requests_number, rt_total):
    return {
        "overall": {
            "interval_real": {"len": requests_number, "total": rt_total},
        },
    }


@pytest.mark.parametrize('requests_number, rt_total', [(0, 0), (1, 0)])
def test_avg_time_notify_handles_zero_requests(requests_number, rt_total):
    criterion = AvgTimeCriterion(autostop=None, param_str='100ms, 5s')
    data = get_data(requests_number, rt_total)
    assert criterion.notify(data, stat=None) is False
