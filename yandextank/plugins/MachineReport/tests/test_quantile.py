"""Reference for the window quantile of machine_report.v1 ($defs/latencyMs): nearest rank over merged hist.v1 lines.

The plugin (T3) must agree with merged_quantile, and latency_ms of its report with latency_ms here. The examples are
the counterexamples from the review, where linear interpolation (np.percentile default) differs from the bin edge
by far more than a bin.
"""

import numpy as np
import pytest

from yandextank.aggregator.aggregator import Worker

GRID = Worker({}, True).bins


def hist_line(values_us):
    """One hist.v1 line as the plugin writes it: the aggregator histogram plus what it drops beyond the grid."""
    data = Worker({}, True)._histogram(np.asarray(values_us, dtype=float))
    return {'upper_us': data['bins'], 'counts': data['data'], 'overflow': len(values_us) - sum(data['data'])}


def merged_quantile(lines, p):
    """Upper edge of the first bin where the cumulative count reaches k = ceil(p * n / 100); None in the overflow."""
    merged = {}
    overflow = 0
    for line in lines:
        overflow += line['overflow']
        for upper, count in zip(line['upper_us'], line['counts']):
            merged[upper] = merged.get(upper, 0) + count
    n = sum(merged.values()) + overflow
    k = -(-p * n // 100)  # exact ceil for integer p
    cumulative = 0
    for upper in sorted(merged):
        cumulative += merged[upper]
        if cumulative >= k:
            return upper
    return None


def latency_ms(lines, ps=(50, 90, 95, 99, 100)):
    """latency_ms of a report window: merged_quantile in milliseconds (upper_us / 1000), None in the overflow."""
    quantiles = {'p{}'.format(p): merged_quantile(lines, p) for p in ps}
    return {key: None if upper is None else upper / 1000 for key, upper in quantiles.items()}


def bin_width(value_us):
    i = np.searchsorted(GRID, value_us, side='right')
    return GRID[i] - GRID[i - 1]


@pytest.mark.parametrize(
    'values, p, expected',
    [
        ([1000] * 99 + [100000], 99, 1010),  # np.percentile default gives 1990
        ([1001, 1000001], 50, 1010),  # np.percentile default gives 500501
        ([1000000, 301000000], 50, 1005000),
        ([1000000, 301000000], 100, None),  # rank in the overflow; the exact max is latency_max_ms
        ([1000000, 301000000], 99, None),
        ([300000000], 100, 300000000),  # the last edge is inclusive in np.histogram
    ],
)
def test_review_examples(values, p, expected):
    assert merged_quantile([hist_line(values)], p) == expected


def test_latency_ms_in_milliseconds():
    # spec scenario: one response of 1 s and one of 301 s
    assert latency_ms([hist_line([1000000, 301000000])], (50, 99, 100)) == {'p50': 1005.0, 'p99': None, 'p100': None}


def test_discarded_shots_not_in_histogram():
    """Discarded shots (net code 777, interval_real 0) are not responses: counting them would pull p50 down to 30 ms."""
    phout = [(0, 777)] * 300 + [(v, 0) for v in np.linspace(10000, 79000, 700)]
    responses = [value for value, net in phout if net != 777]
    assert merged_quantile([hist_line(responses)], 50) == 45000
    assert merged_quantile([hist_line([value for value, _ in phout])], 50) == 30000


def test_bound_against_inverted_cdf():
    """0 <= merged - reference <= width of the bin holding the reference, for any n, merging per-second lines."""
    rng = np.random.default_rng(3805)
    for n in (1, 2, 3, 5, 10, 50, 300):
        for _ in range(200):
            values = np.round(np.exp(rng.normal(np.log(20000), 1.5, n)))
            seconds = np.array_split(values, min(n, 4))
            lines = [hist_line(s) for s in seconds if len(s)]
            ps = (50, 75, 90, 95, 98, 99, 100)
            refs = np.percentile(values, ps, method='inverted_cdf')  # один вызов на выборку вместо семи
            for p, ref in zip(ps, refs):
                got = merged_quantile(lines, p)
                assert 0 <= got - ref <= bin_width(ref), (n, p, got, ref)
