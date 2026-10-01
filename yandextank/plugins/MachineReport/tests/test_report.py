"""report.build and its inputs. Seconds come from the real tank aggregation (string_to_df, DataPoller, TimeChopper,
Aggregator, TankAggregator); every report is checked by the schemas and the copy of report.Validate in
test_schema.py, and its quantiles against numpy.percentile(method='inverted_cdf') over the raw phout rows."""

import functools
import gzip
import os
import time
from fractions import Fraction

import numpy as np
import pytest

from yandextank.aggregator import TankAggregator
from yandextank.aggregator.aggregator import Aggregator, DataPoller
from yandextank.aggregator.chopper import TimeChopper
from yandextank.plugins.MachineReport import report
from yandextank.plugins.Phantom.reader import string_to_df

from test_quantile import bin_width, hist_line
from test_quantile import latency_ms as reference_latency_ms
from test_schema import errors, source, validator

AGGR_CONFIG = TankAggregator.load_config()
T = 1790000000


def const(ops, duration):
    return {'type': 'const', 'ops': ops, 'duration': duration}


def line(low, high, duration):
    return {'type': 'line', 'from': low, 'to': high, 'duration': duration}


def once(times):
    return {'type': 'once', 'times': times}


def step(low, high, by, duration):
    return {'type': 'step', 'from': low, 'to': high, 'step': by, 'duration': duration}


def pandora_pool(rps, gun=None, ammo=None, startup=None):
    return {
        'gun': gun or {'type': 'http', 'target': 'target:80'},
        'ammo': ammo or {'type': 'uri', 'uris': ['/']},
        'rps': rps,
        'startup': startup or once(10),
    }


def pools(*schedules):
    return report.pandora_pools([pandora_pool(rps) for rps in schedules])


def phout(rows):
    """Phout text of (send_ts, tag, interval_real_us, net_code, proto_code) rows."""
    return ''.join(
        '{:.6f}\t{}\t{}\t0\t0\t0\t0\t0\t0\t0\t{}\t{}\n'.format(ts, tag, int(round(us)), net, proto)
        for ts, tag, us, net, proto in rows
    )


def aggregate(sources, poll_period=0.001, max_wait=31):
    """Seconds of the tank aggregator: a source per pool, an item per poll (phout text or None for an empty poll)."""
    pollers = [
        DataPoller(poll_period=poll_period, max_wait=max_wait).poll(string_to_df(c) if c else None for c in chunks)
        for chunks in sources
    ]
    return list(Aggregator(TimeChopper(pollers), AGGR_CONFIG))


def summarize(data, instances=10):
    seconds, lines = [], []
    for d in data:
        s, hist = report.summarize_second(d, {'ts': d['ts'], 'metrics': {'instances': instances, 'reqps': 0}})
        seconds.append(s)
        lines += hist
    return seconds, lines


def context(pools, **overrides):
    ctx = {
        'pools': pools,
        'trim_s': 15,
        'provenance': {
            'plugin_version': report.PLUGIN_VERSION,
            'tank_version': '2.1.16',
            'config_sha256': '0' * 64,
            'labels': {},
            'series': None,
            'test_id': None,
            'tank_job_id': 'job',
            'run_id': None,
            'created_at': '2026-09-30T00:00:00Z',
        },
        'statuses': {'shooting': {'status': 'DONE', 'retcode': 0, 'autostop_criterion': None}},
        'gun': {'type': 'pandora', 'version': '0.8.3'},
        'autostop_criteria': [],
        'histograms': {'path': report.HIST_FILE, 'format': 'hist.v1', 'sha256': '0' * 64, 'bytes': 0, 'lines': 0},
        'monitoring': [],
        'points': {},
        'tolerance_s': 60,
        'generator': {'host': 'generator', 'dc': None, 'cpu_model': None, 'cores': 1},
        'cpu': {'source': 'unavailable', 'snapshots': []},
        'saturation': {
            'cpu_util_pct': 90,
            'cpu_throttled_periods_pct': 5,
            'discarded_shots_pct': 1,
            'plan_deficit_pct': 5,
            'sustain_s': 60,
        },
        'target': {'address': 'target:80', 'hosts': []},
        'target_cpu': None,
        'perforator': {'status': 'not_requested'},
    }
    ctx.update(overrides)
    return ctx


def build(rows, schedule_pools, **ctx):
    """Report and hist lines of phout rows shot by the pools; both pass their schemas and report.Validate."""
    seconds, lines = summarize(aggregate([[phout(rows)]]))
    doc = report.build(seconds, lines, context(schedule_pools, **ctx))
    assert not errors(validator('machine_report'), 'machine_report', doc)
    v = validator('hist')
    for li in lines:
        assert not errors(v, 'hist', li), li
    return doc


def window(doc, id):
    return next(w for w in doc['windows'] if w['id'] == id)


def assert_reference(agg, values_us):
    """The contract bound: 0 <= merged - inverted_cdf <= width of the bin holding the reference, null in overflow."""
    values = np.asarray(values_us, dtype=float)
    assert agg['responses'] == len(values)
    if not len(values):
        assert agg['latency_ms'] is None
        return
    assert agg['latency_max_ms'] == pytest.approx(values.max() / 1000)
    assert agg['latency_overflow'] == int((values > report.GRID[-1]).sum())
    for key, got in agg['latency_ms'].items():
        ref = np.percentile(values, float(key[1:]), method='inverted_cdf')
        if ref > report.GRID[-1]:
            assert got is None, key
        else:
            assert 0 <= round(got * 1000) - ref <= bin_width(ref), (key, got, ref)


def assert_windows_match_phout(doc, df):
    """Every window and case against the raw rows received in it (discarded shots excluded)."""
    sent = df[df.net_code != 777]
    for w in doc['windows']:
        rows = sent[(sent.index >= w['start_ts']) & (sent.index < w['end_ts'])]
        assert_reference(w, rows.interval_real)
        assert sorted(w['cases']) == sorted(set(rows.tag.dropna()) - {report.DISCARDED_TAG, report.EMPTY_TAG})
        for tag, case in w['cases'].items():
            assert_reference(case, rows[rows.tag == tag].interval_real)


# Spec scenarios


def test_two_responses_nearest_rank():
    doc = build([(T + 0.1, 'a', 1001, 0, 200), (T - 0.9, 'a', 1000001, 0, 200)], pools([const(10, '10s')]))
    assert window(doc, 'test')['latency_ms']['p50'] == 1.01


def test_response_beyond_grid():
    doc = build([(T - 1, 'a', 1e6, 0, 200), (T - 301, 'a', 301e6, 0, 200)], pools([const(10, '10s')]))
    test = window(doc, 'test')
    assert (test['responses'], test['latency_overflow'], test['latency_max_ms']) == (2, 1, 301000)
    assert (test['latency_ms']['p50'], test['latency_ms']['p99'], test['latency_ms']['p100']) == (1005, None, None)


def test_discarded_shots():
    rows = [(T + 0.001 * i, 'work', us, 0, 200) for i, us in enumerate(np.linspace(10000, 79000, 700))]
    rows += [(T + 0.5, report.DISCARDED_TAG, 0, 777, 0)] * 300
    doc = build(rows, pools([const(1000, '10s')]))
    test = window(doc, 'test')
    assert test['responses'] == 700
    assert test['net_codes'] == {'0': 700, '777': 300}
    assert test['http_codes'] == {'200': 700}
    assert test['latency_ms']['p50'] == 45
    assert list(test['cases']) == ['work']
    assert doc['load']['per_second'][0]['rps'] == 700


def test_discarded_attribution_checked():
    """777 outside the discarded tag or other codes in it would put unsent shots into the quantiles."""
    for rows in ([(T, 'work', 0, 777, 0)], [(T, report.DISCARDED_TAG, 0, 0, 0)]):
        (data,) = aggregate([[phout(rows)]])
        with pytest.raises(ValueError):
            report.summarize_second(data, None)


def test_initial_pause():
    rows = [(T + s + 0.01 * i, 'a', 1000, 0, 200) for s in range(5) for i in range(5)]
    doc = build(rows, pools([const(0, '10s'), const(100, '60s')]))
    assert window(doc, 'test')['start_ts'] == T - 10
    assert window(doc, 'phase-1')['start_ts'] == T
    pause = doc['load']['per_second'][:10]
    assert [(s['rps'], s['planned_rps'], s['instances']) for s in pause] == [(0, 0, None)] * 10


def test_initial_step_from_zero():
    """pandora step makes const(from, duration) its first level: step from 0 opens the schedule with a pause."""
    rows = [(T + s + 0.1 * i, 'a', 1000, 0, 200) for s in range(5) for i in range(10)]
    doc = build(rows, pools([step(0, 20, 10, '20s')]))
    assert window(doc, 'test')['start_ts'] == T - 20


def test_once_phase_and_second_without_responses():
    """once at offset 5 whose second got no response: a 1 s window with 0 responses; per_second has no hole."""
    rows = [(T + s + 0.01 * i, 'a', 1000, 0, 200) for s in list(range(5)) + list(range(6, 11)) for i in range(10)]
    doc = build(rows, pools([const(10, '5s'), once(1), const(10, '5s')]))
    phase = window(doc, 'phase-1')
    assert (phase['end_ts'] - phase['start_ts'], phase['responses'], phase['latency_ms'], phase['rps_mean']) == (
        1,
        0,
        None,
        0,
    )
    hole = doc['load']['per_second'][5]
    assert (hole['ts'], hole['rps'], hole['net_codes'], hole['http_codes'], hole['instances']) == (
        T + 5,
        0,
        {},
        {},
        None,
    )
    assert hole['planned_rps'] == 11  # once(1) and the first second of the next const(10)


def test_phase_started_in_the_last_second():
    rows = [(T + s + 0.1 * i, 'a', 1000, 0, 200) for s in range(11) for i in range(10)]
    doc = build(rows, pools([const(10, '10s'), const(20, '10s')]))
    phase = window(doc, 'phase-1')
    assert (phase['start_ts'], phase['end_ts']) == (T + 10, T + 11)


def test_response_tail_after_stop():
    """Autostop 2 s before phase 2, responses come 5 s more: the phase has started and has a short window."""
    rows = [(T + 0.1 * i, 'a', 1000, 0, 200) for i in range(180)]
    rows += [(T + 17.5 + 0.1 * i, 'a', 5e6, 0, 200) for i in range(5)]
    doc = build(rows, pools([const(10, '10s'), const(10, '10s'), const(10, '10s')]))
    assert window(doc, 'test')['end_ts'] == T + 23
    phase = window(doc, 'phase-2')
    assert (phase['start_ts'], phase['end_ts']) == (T + 20, T + 23)
    assert 'steady-2' not in [w['id'] for w in doc['windows']]


def test_phases_after_autostop_have_no_windows():
    rows = [(T + 0.1 * i, 'a', 1000, 0, 200) for i in range(80)]
    doc = build(rows, pools([const(10, '10s'), const(10, '10s'), const(10, '10s')]))
    assert [w['id'] for w in doc['windows']] == ['test', 'phase-0']


def test_two_pools():
    rows = [(T + 0.01 * i, 'a', 1000, 0, 200) for i in range(300)]
    doc = build(rows, pools([line(1, 100, '60s'), const(100, '300s')], [const(20, '360s')]))
    assert [(p['index'], p['pool']) for p in doc['phases']] == [(0, 0), (1, 0), (2, 1)]
    assert doc['load']['per_second'][0]['planned_rps'] == pytest.approx(1 + 99 / 120 + 20)
    assert len(doc['provenance']['load_profile']['pools']) == 2


@pytest.mark.parametrize('delay', [10, 20])
def test_slow_first_responses(delay):
    """const(1) from T; the shots of the first `delay` seconds answer in 30 s, the rest in 10 ms. S is the first
    response second, T + delay; steady-0 stays in the phase of the schedule while delay <= trim (15 s) and runs
    into the next phase by delay - trim otherwise (the known limit of S)."""
    rows = [(T + k, 'a', 30e6 if k < delay else 10000, 0, 200) for k in range(60)]
    rows += [(T + 60 + 0.5 * k, 'a', 10000, 0, 200) for k in range(120)]
    doc = build(rows, pools([const(1, '60s'), const(2, '60s')]))
    test, steady = window(doc, 'test'), window(doc, 'steady-0')
    assert test['start_ts'] == T + delay
    assert test['responses'] == 180
    assert steady['end_ts'] == T + delay + 60 - 15
    assert (steady['end_ts'] <= T + 60) == (delay <= 15)


def test_seconds_in_any_order_and_repeated():
    """Late rows of a second make the chopper yield its ts again; callbacks may come in any order."""
    rows = [(T + s + 0.01 * i, 'a', 1000 + 10 * i, 0, 200) for s in range(20) for i in range(20)]
    once_seconds, once_lines = summarize(aggregate([[phout(rows)]]))
    is_late = [5 <= k // 20 < 10 and k % 2 == 1 for k in range(len(rows))]
    late = [r for r, lt in zip(rows, is_late) if lt]
    early = [r for r, lt in zip(rows, is_late) if not lt]
    first_chunk = phout(r for r in early if r[0] < T + 10)
    data = aggregate([[first_chunk, phout(late + [r for r in early if r[0] >= T + 10])]])
    assert len(data) > len({d['ts'] for d in data})
    seconds, lines = summarize(data)
    schedule = pools([const(20, '20s')])
    assert report.build(seconds[::-1], lines, context(schedule)) == report.build(
        once_seconds, once_lines, context(schedule)
    )


def test_no_seconds_no_report():
    with pytest.raises(report.NoReport):
        report.build([], [], context(pools([const(1, '1s')])))


def test_stray_timestamp_no_report():
    """One receive ts far past the schedule would make the report span it second by second."""
    seconds, lines = summarize(aggregate([[phout([(T, 'a', 1000, 0, 200), (T + 1e7, 'a', 1000, 0, 200)])]]))
    started = time.time()
    with pytest.raises(report.NoReport, match='stray'):
        report.build(seconds, lines, context(pools([const(1, '10s')])))
    assert time.time() - started < 1


def test_no_steady_for_zero_const():
    rows = [(T + s + 0.1 * i, 'a', 1000, 0, 200) for s in list(range(20)) + list(range(40, 60)) for i in range(10)]
    doc = build(rows, pools([const(10, '20s'), const(0, '20s'), const(10, '20s')]), trim_s=5)
    assert [w['id'] for w in doc['windows'] if w['kind'] == 'steady'] == ['steady-0', 'steady-2']


def test_empty_tag_is_not_a_case():
    """pandora tags a shot without a tag __EMPTY__: its responses are in the line without a case only."""
    rows = [(T + 0.1 * i, report.EMPTY_TAG, 1000, 0, 200) for i in range(5)] + [(T + 0.5, 'a', 2000, 0, 200)]
    (data,) = aggregate([[phout(rows)]])
    summary, lines = report.summarize_second(data, None)
    assert (summary['responses'], list(summary['cases'])) == (6, ['a'])
    assert [li['case'] for li in lines] == [None, 'a']


# Replay through the real aggregation


def test_replay_recorded_phout():
    """70 s of a real pandora run without tags: line(1,120,30s) then const(120,180s), cut like an autostop."""
    with gzip.open(source('tests', 'fixtures', 'phout', 'pandora_line_const_70s.phout.gz'), 'rt') as f:
        text = f.read()
    rows = text.splitlines(True)
    data = aggregate([[''.join(rows[i : i + 500]) for i in range(0, len(rows), 500)]])
    seconds, lines = summarize(data)
    schedule = pools([line(1, 120, '30s'), const(120, '180s')])
    doc = report.build(seconds, lines, context(schedule))
    assert not errors(validator('machine_report'), 'machine_report', doc)
    assert [w['id'] for w in doc['windows']] == ['test', 'phase-0', 'phase-1', 'steady-1']
    start, end = window(doc, 'test')['start_ts'], window(doc, 'test')['end_ts']
    assert [(window(doc, id)['start_ts'], window(doc, id)['end_ts']) for id in ('phase-0', 'phase-1', 'steady-1')] == [
        (start, start + 30),
        (start + 30, end),
        (start + 30 + 15, min(end, start + 210) - 15),
    ]
    df = string_to_df(text)
    assert window(doc, 'test')['responses'] == len(df)
    assert_windows_match_phout(doc, df)
    per_second = df.groupby(level=0).size()
    assert [s['rps'] for s in doc['load']['per_second']] == [
        int(per_second.get(s['ts'], 0)) for s in doc['load']['per_second']
    ]


def test_replay_synthetic_phout_with_cases_discarded_and_overflow():
    rng = np.random.default_rng(3806)
    rows = []
    for k in range(4000):
        send = T + k * 0.01
        if k % 13 == 0:
            rows.append((send, report.DISCARDED_TAG, 0, 777, 0))
        elif k % 997 == 0:
            rows.append((send - 305, 'slow', 305e6, 0, 200))
        else:
            tag = 'first' if k % 3 else 'second'
            net, proto = (110, 0) if k % 101 == 0 else (0, 503 if k % 17 == 0 else 200)
            rows.append((send, tag, float(np.round(np.exp(rng.normal(np.log(20000), 1.2)))), net, proto))
    chunks = [phout(rows[i : i + 300]) for i in range(0, len(rows), 300)]
    seconds, lines = summarize(aggregate([chunks]))
    doc = report.build(seconds, lines, context(pools([const(100, '10s'), const(100, '30s')])))
    assert not errors(validator('machine_report'), 'machine_report', doc)
    assert window(doc, 'test')['latency_overflow'] == 4
    assert_windows_match_phout(doc, string_to_df(phout(rows)))


def test_tank_aggregator_order_and_missing_stats():
    """Real TankAggregator: a second without stats and the tail without stats come at end_test after later
    seconds; a second without responses is never delivered. per_second has no holes, instances is null there."""
    seconds_with_data = [s for s in range(10) if s != 4]
    chunks = [phout([(T + s + 0.1 * i, 'a', 1000, 0, 200) for i in range(5)]) for s in seconds_with_data]
    stats = [{'ts': T + s, 'metrics': {'instances': 7, 'reqps': 5}} for s in range(8) if s != 2]

    class Stats(object):
        def __init__(self):
            self.items = list(stats)

        def __iter__(self):
            return self

        def __next__(self):
            if not self.items:
                raise StopIteration
            return [self.items.pop(0)]

        def close(self):
            pass

    class Generator(object):
        def get_reader(self):
            return [iter(string_to_df(c) for c in chunks)]

        def get_stats_reader(self):
            return Stats()

        def end_test(self, retcode):
            return retcode

    delivered = []

    class Listener(object):
        def on_aggregated_data(self, data, stat):
            delivered.append(report.summarize_second(data, stat))

    aggregator = TankAggregator(Generator(), DataPoller(poll_period=0.001, max_wait=1))
    aggregator.add_result_listener(Listener())
    aggregator.start_test()
    deadline = time.time() + 30
    while aggregator.is_test_finished() < 0 and time.time() < deadline:
        time.sleep(0.01)
    aggregator.end_test(0)
    order = [s['ts'] - T for s, _ in delivered]
    assert sorted(order) == seconds_with_data and order != sorted(order)
    seconds = [s for s, _ in delivered]
    lines = [li for _, hist in delivered for li in hist]
    doc = report.build(seconds, lines, context(pools([const(5, '10s')])))
    assert not errors(validator('machine_report'), 'machine_report', doc)
    per_second = doc['load']['per_second']
    assert [s['ts'] - T for s in per_second] == list(range(10))
    assert [s['instances'] for s in per_second] == [7, 7, None, 7, None, 7, 7, 7, None, None]
    assert per_second[4]['rps'] == 0


def test_two_pools_with_a_pause_through_poller_and_chopper():
    """Two pool sources. A silence before the first data of a pool loses nothing, however long; a silence after it
    longer than max_wait drops the pool until the end (R13), which check_pauses rules out by the schedule."""
    first = [phout([(T + s + 0.1 * i, 'a', 1000, 0, 200) for i in range(10)]) for s in range(20)]
    late = [phout([(T + s + 0.5, 'b', 2000, 0, 200)]) for s in range(10, 20)]
    kept = aggregate([first, [None] * 30 + late], max_wait=0.01)
    assert sum(d['overall']['interval_real']['len'] for d in kept) == 210
    seconds, lines = summarize(kept)
    schedule = report.pandora_pools(
        [pandora_pool([const(10, '20s')]), pandora_pool([const(0, '10s'), const(1, '10s')])]
    )
    report.check_pauses(schedule, 31)
    doc = report.build(seconds, lines, context(schedule))
    assert not errors(validator('machine_report'), 'machine_report', doc)
    assert window(doc, 'test')['cases']['b']['responses'] == 10
    early = [phout([(T + s + 0.5, 'b', 2000, 0, 200)]) for s in range(5)]
    dropped = aggregate([first, early + [None] * 30 + late], max_wait=0.01)
    assert sum(d['overall']['interval_real']['len'] for d in dropped) == 205
    with pytest.raises(report.NoReport):
        report.check_pauses(pools([const(1, '5s'), const(0, '40s'), const(1, '10s')]), 31)


# Load profile


@pytest.mark.parametrize(
    'step, text',
    [
        (const(10, '1m'), 'const(10,60s)'),
        (const(10, '60s'), 'const(10,60s)'),
        (const(0.5, '3h2m3s'), 'const(0.5,10923s)'),
        (const(1.0, '1500ms'), 'const(1,1.5s)'),
        (line(1, 10, '5m'), 'line(1,10,300s)'),
        ({'type': 'unlimited', 'duration': '0.3s'}, 'unlimited(0.3s)'),
        (once(1), 'once(1)'),
        ({'type': 'step', 'from': 10, 'to': 50, 'step': 10, 'duration': '30s'}, 'step(10,50,10,30s)'),
        (
            {'type': 'instance_step', 'from': 10, 'to': 100, 'step': 10, 'stepduration': '1s'},
            'instance_step(10,100,10,1s)',
        ),
    ],
)
def test_schedule_normalization(step, text):
    ((_, _, got),) = report.parse_steps(step)
    assert got == text
    assert report.PROFILE_STRING.match(got)


@pytest.mark.parametrize('step', [const(10, 60), const(10, '1 min'), const('10', '1m'), line(1, 2, '')])
def test_bad_schedule(step):
    with pytest.raises(ValueError):
        report.parse_steps(step)


def test_unsupported_schedule():
    with pytest.raises(report.NoReport):
        report.parse_steps({'type': 'composite', 'nested': []}, report.RPS_STEPS)


def profile(**pool):
    (p,) = report.pandora_pools([pandora_pool(**dict({'rps': [const(10, '1m')]}, **pool))])
    return p.profile


def test_pool_options_load_profile_cannot_express():
    """rps-per-instance multiplies the schedule, discard_overflow: false delays shots: v1 would give both the hash
    of an ordinary rps pool."""
    for option in ({'rps-per-instance': True}, {'discard_overflow': False}):
        with pytest.raises(report.NoReport):
            report.pandora_pools([dict(pandora_pool([const(10, '1m')]), **option)])
    report.pandora_pools(
        [dict(pandora_pool([const(10, '1m')]), **{'rps-per-instance': False, 'discard_overflow': True})]
    )


def test_load_profile_hash():
    base = report.json_sha256({'pools': [profile()]})
    assert report.json_sha256({'pools': [profile(rps=[const(10, '60s')])]}) == base
    assert report.json_sha256({'pools': [profile(ammo={'type': 'uri', 'uris': ['/other']})]}) != base
    assert report.json_sha256({'pools': [profile(rps=[const(20, '60s')])]}) != base
    assert report.json_sha256({'pools': [profile(startup=once(20))]}) != base


def test_ammo_file_hash_by_bytes(tmp_path):
    paths = [tmp_path / name for name in ('a', 'b', 'c')]
    for path, content in zip(paths, (b'GET / HTTP/1.1\n', b'GET / HTTP/1.1\n', b'GET /x HTTP/1.1\n')):
        path.write_bytes(content)
    a, b, c = [profile(ammo={'type': 'raw', 'file': str(path)}) for path in paths]
    assert a == b != c
    assert a['ammo_sha256'] == report.file_sha256(str(paths[0]))
    assert profile(ammo={'type': 'dummy'})['ammo_sha256'] is None


def test_inline_ammo_hash():
    uris = ['/b', '/\u0430']
    expected = report.json_sha256(uris, ensure_ascii=False)
    assert profile(ammo={'type': 'uri', 'uris': uris})['ammo_sha256'] == expected


@pytest.mark.parametrize(
    'guns, overrides, protocols, status',
    [
        ([{'type': 'http'}], [], [('http1', 'http')], 'not_applicable'),
        ([{'type': 'http', 'ssl': True}], [], [('http1_tls', 'http')], 'not_applicable'),
        ([{'type': 'http2'}], [], [('h2c', 'grpc')], 'not_read'),
        ([{'type': 'http2'}], [{'target_protocol': 'http'}], [('h2c', 'http')], 'not_applicable'),
        ([{'type': 'http2', 'ssl': True}], [], [('h2', 'http')], 'not_applicable'),
        ([{'type': 'grpc'}], [], [('h2c', 'grpc')], 'http_mapped'),
        ([{'type': 'grpc', 'tls': True}], [], [('h2', 'grpc')], 'http_mapped'),
        ([{'type': 'grpc'}, {'type': 'http2'}], [], [('h2c', 'grpc'), ('h2c', 'grpc')], 'not_read'),
        ([{'type': 'grpc'}, {'type': 'http'}], [{}, {}], [('h2c', 'grpc'), ('http1', 'http')], 'http_mapped'),
        ([{'type': 'my_gun'}], [], [('other', 'other')], 'not_applicable'),
    ],
)
def test_protocols(guns, overrides, protocols, status):
    result = report.pandora_pools([pandora_pool([const(1, '1s')], gun=g) for g in guns], overrides)
    assert [(p.profile['transport'], p.profile['target_protocol']) for p in result] == protocols
    assert report.grpc_status(result) == status


@pytest.mark.parametrize(
    'startup, instances',
    [
        (once(10), 10),
        ([once(10), once(5)], 15),
        ({'type': 'instance_step', 'from': 10, 'to': 100, 'step': 10, 'stepduration': '1s'}, 100),
        ({'type': 'instance_step', 'from': 10, 'to': 95, 'step': 10, 'stepduration': '1s'}, 90),
        # an instance per shot of the startup schedule, as pandora starts them
        (const(10, '10s'), 100),
        ([once(2), line(0, 10, '2s')], 12),
        ({'type': 'unlimited', 'duration': '10s'}, None),
    ],
)
def test_startup_instances(startup, instances):
    assert profile(startup=startup)['instances'] == instances


def test_plan():
    (pool,) = pools([line(1, 120, '30s'), const(120, '10s'), once(5), {'type': 'unlimited', 'duration': '2s'}])
    plan = pool.plan()
    assert plan[0] == 1 + Fraction(119, 60)
    assert plan[35] == 120
    assert plan[40] is None and plan[41] is None
    assert pool.plan().get(42, 0) == 0
    (step,) = pools([{'type': 'step', 'from': 10, 'to': 30, 'step': 10, 'duration': '2s'}])
    assert [step.plan()[s] for s in range(6)] == [10, 10, 20, 20, 30, 30]
    (half,) = pools([const(3, '1.5s'), const(1, '1s')])
    assert [half.plan()[s] for s in range(3)] == [3, Fraction(3, 2) + Fraction(1, 2), Fraction(1, 2)]


@pytest.mark.parametrize(
    'schedules, pause',
    [
        # before the first shot and after the last one
        ([[const(0, '150s'), line(1000, 3000, '15m')]], False),
        ([[step(0, 20, 10, '60s')]], False),
        ([[once(1)], [const(100, '600s')]], False),
        ([[const(100, '60s'), const(0, '100s')]], False),
        # between shots
        ([[once(1), const(0, '31s'), once(1)]], True),
        ([[once(1), const(0, '30s'), once(1)]], False),
        ([[const(10, '10s'), const(0, '10s'), line(0, 0, '25s'), const(10, '10s')]], True),
        ([[const(10, '10s'), step(0, 20, 10, '40s')]], True),
        ([[const(0.02, '120s')]], True),
        ([[line(0, 1, '120s')]], False),
        ([[line(0, 0.1, '600s')]], True),
        ([[line(0.1, 0, '600s')]], True),
    ],
)
def test_aggregator_max_wait(schedules, pause):
    check = lambda: report.check_pauses(pools(*schedules), 31)  # noqa: E731
    if pause:
        with pytest.raises(report.NoReport):
            check()
    else:
        check()


# Provenance


def test_config_hash_masks_secrets():
    def config(token, labels=None):
        return {
            'pandora': {
                'config_content': {
                    'pools': [
                        {
                            'ammo': {'headers': ['[Host: target]', '[Authorization: OAuth {}]'.format(token)]},
                            'gun': {'target': 'target:80'},
                        }
                    ]
                },
            },
            'uploader': {'token_file': token, 'api': 'https://api/v1?oauth_token={}&x=1'.format(token)},
            'metaconf': {'firestarter': {'labels': labels or {'run': 'a'}, 'auth_secret': token}},
        }

    assert report.config_sha256(config('one')) == report.config_sha256(config('two'))
    assert report.config_sha256(config('one', {'run': 'b'})) != report.config_sha256(config('one'))
    masked = report.mask(config('secret-value'))
    assert 'secret-value' not in str(masked)
    assert masked['pandora']['config_content']['pools'][0]['ammo']['headers'] == [
        '[Host: target]',
        '[Authorization: ***]',
    ]
    assert masked['uploader']['api'] == 'https://api/v1?oauth_token=***&x=1'


@pytest.mark.parametrize(
    'dc, dc_env, environ, expected',
    [
        ('dc-b', ['NODE_DC'], {'NODE_DC': 'dc-a'}, 'dc-b'),
        (None, ['NODE_DC', 'NODE_CLUSTER'], {'NODE_DC': 'dc-a', 'NODE_CLUSTER': 'dc-c.cluster.example'}, 'dc-a'),
        (None, ['NODE_DC', 'NODE_CLUSTER'], {'NODE_DC': '', 'NODE_CLUSTER': 'dc-c.cluster.example'}, 'dc-c'),
        (None, ['NODE_DC'], {}, None),
        (None, [], {'NODE_DC': 'dc-a'}, None),  # no names configured: the plugin reads no variables
    ],
)
def test_generator_dc(dc, dc_env, environ, expected):
    assert report.generator_dc(dc, dc_env, environ) == expected


def test_completeness():
    source = {'id': 's', 'required': False, 'status': 'ok'}
    assert report.completeness([])['status'] == 'COMPLETE'
    assert report.completeness([dict(source, status='unsupported')])['status'] == 'PARTIAL'
    # an optional source without its Solomon panel was not requested: the report stays COMPLETE
    assert report.completeness([source, dict(source, status='not_requested')])['status'] == 'COMPLETE'
    assert report.completeness([dict(source, required=True, status='unsupported')]) == {
        'status': 'INCOMPLETE',
        'blocking': True,
        'blocking_sources': ['s'],
    }


def test_latency_agrees_with_reference_merge():
    """latency_ms of a window equals test_quantile.latency_ms over the same hist.v1 lines, overflow included."""
    rng = np.random.default_rng(3806)
    for n in (1, 2, 7, 100, 1000):
        values = np.round(np.exp(rng.normal(np.log(20000), 3, n)))
        lines = [hist_line(chunk) for chunk in np.array_split(values, min(n, 5))]
        counts = np.zeros(len(report.GRID), dtype=np.int64)
        for li in lines:
            counts[[report.GRID_INDEX[int(u)] for u in li['upper_us']]] += np.asarray(li['counts'], dtype=np.int64)
        overflow = sum(li['overflow'] for li in lines)
        ps = tuple(int(p) for p in report.QUANTILES)
        assert report.latency_ms(counts, overflow, n) == reference_latency_ms(lines, ps)


# Monitoring


def spec(host='h', metrics=('m',), kind='telegraf', **fields):
    return dict(
        {'id': host, 'kind': kind, 'entity': 'target', 'host': host, 'required': False},
        metrics=[{'name': m, 'unit': 'none'} for m in metrics],
        **fields,
    )


def evaluate(points, specs=None, start=0, end=300, tolerance=60):
    """Sources over points {ts: {metric: value}} of chunk key h in a test window [start, end) with a steady window."""
    windows = [report._Window('test', 'test', None, start, end), report._Window('steady-0', 'steady', 0, 100, 200)]
    return report.monitoring(specs or [spec()], {'h': points}, windows, start, end, tolerance)


def series(ts, value=1.0):
    return {t: {'m': value} for t in ts}


@pytest.mark.parametrize(
    'ts, tolerance, status, reason',
    [
        (range(300), 60, 'ok', None),
        # irregular steps 1, 2, 1, 2, 3 s: median 2 s, no gap over 4 s
        (np.cumsum([1, 2, 1, 2, 3] * 33)[:-1] - 1, 60, 'ok', None),
        # the Solomon grid of 15 s with the last point 28 s before E, as in step 0
        (range(3, 273, 15), 60, 'ok', None),
        # late points at the right edge within the tolerance; without it they are a gap
        (range(250), 60, 'ok', None),
        (range(250), 30, 'partial', 'a gap of 21 s, over two median steps of 1 s'),
        ([t for t in range(300) if not 100 <= t < 140], 60, 'partial', 'a gap of 41 s, over two median steps of 1 s'),
        (range(10, 300), 60, 'partial', 'a gap of 10 s, over two median steps of 1 s'),
        ([t for t in range(300) if t not in (100, 101)], 60, 'partial', 'a gap of 3 s, over two median steps of 1 s'),
        # a late point past E - tolerance: the gap to it lies within the tolerance and does not count
        (list(range(0, 241, 15)) + [285], 60, 'ok', None),
        ([150], 60, 'partial', 'one point'),
    ],
)
def test_source_coverage(ts, tolerance, status, reason):
    [source] = evaluate(series(int(t) for t in ts), tolerance=tolerance)
    assert (source['status'], source['reason']) == (status, None if reason is None else 'metric m: ' + reason)


def test_points_out_of_the_window_dropped():
    points = series(range(300))
    points.update(series([-5, 300, 302], value=100.0))  # E + 2: the load is gone or half gone
    points[10] = {'m': 'n/a'}  # not a number
    [source] = evaluate(points)
    assert (source['status'], source['points']) == ('ok', 299)
    test = source['metrics'][0]['windows'][0]
    assert test == {'window': 'test', 'points': 299, 'mean': 1.0, 'min': 1.0, 'max': 1.0}


def test_metric_values_by_window():
    [source] = evaluate({t: {'m': float(t), 'other': 0} for t in range(0, 300, 10)})
    assert source['metrics'] == [
        {
            'name': 'm',
            'unit': 'none',
            'windows': [
                {'window': 'test', 'points': 30, 'mean': 145.0, 'min': 0.0, 'max': 290.0},
                {'window': 'steady-0', 'points': 10, 'mean': 145.0, 'min': 100.0, 'max': 190.0},
            ],
        }
    ]


def test_metric_not_received():
    points = series(range(300))
    [source] = evaluate(points, [spec(metrics=('m', 'cpu'))])
    assert (source['status'], source['reason']) == ('partial', 'metric cpu: not received')
    assert [w['points'] for w in source['metrics'][1]['windows']] == [0, 0]
    [source] = evaluate(points, [spec(metrics=('cpu',))])
    assert (source['status'], source['reason'], source['metrics']) == ('empty', 'metric cpu: not received', [])
    [source] = evaluate({}, [spec(metrics=('cpu',))])
    assert (source['status'], source['reason']) == ('empty', 'no points in the test window')
    # a token Solomon rejects gives no points either: the reason says so
    [source] = evaluate({}, [spec(metrics=('cpu',), kind='solomon')])
    assert source['status'] == 'empty' and 'token' in source['reason']


def test_source_without_metrics_counts_points():
    [source] = evaluate({t: {} for t in range(300)}, [spec(metrics=())])
    assert (source['status'], source['points'], source['metrics']) == ('ok', 300, [])


@pytest.mark.parametrize(
    'first, second, clash',
    [
        (('m',), ('m', 'n'), True),
        ((), ('n',), True),  # a source without metrics reads the whole chunk key
        (('m',), ('n',), False),
    ],
)
def test_ambiguous_sources(first, second, clash):
    specs = [spec(metrics=first, id='a'), spec(metrics=second, id='b')]
    sources = evaluate({t: {'m': 1, 'n': 2} for t in range(300)}, specs)
    if clash:
        assert [(s['status'], s['reason']) for s in sources] == [
            ('error', 'ambiguous: source b reads the same metrics of h'),
            ('error', 'ambiguous: source a reads the same metrics of h'),
        ]
    else:
        assert [s['status'] for s in sources] == ['ok', 'ok']


def test_solomon_names_cut_to_100():
    """The tank Solomon collector cuts custom:<name> to 100 characters: a longer name of the section matches the cut
    one, and two names equal in the first 100 characters are one metric."""
    long = 'custom:' + 'cpu-usage-cores_' * 8
    points = {t: {long[:100]: 1.5} for t in range(300)}
    [source] = evaluate(points, [spec(metrics=(long,), kind='solomon')])
    assert (source['status'], source['metrics'][0]['name']) == ('ok', long)
    sources = evaluate(points, [spec(metrics=(long,), kind='solomon', id='a'), spec(metrics=(long + 'x',), id='b')])
    assert [s['status'] for s in sources] == ['ok', 'empty']  # telegraf names are not cut: b reads another metric
    sources = evaluate(
        points, [spec(metrics=(long,), kind='solomon', id='a'), spec(metrics=(long + 'x',), kind='monium', id='b')]
    )
    assert [s['status'] for s in sources] == ['error', 'error']
    # the YCMonitoring plugin passes its names through convert_name too
    [source] = evaluate(points, [spec(metrics=(long,), kind='yc_monitoring')])
    assert source['status'] == 'ok'


@pytest.mark.parametrize(
    'query, single',
    [
        ('series_sum({service="svc", name="cpu.usage.cores", host="*"})', True),
        (' series_avg( {a="b|c"} ) ', True),
        ('series_max(series_sum({a="(x)"}))', True),
        ('{service="svc", name="cpu.usage.cores"}', False),
        ('series_sum("host", {a="b"})', False),  # grouped by host: a series per host
        ('series_sum( "host", {a="b"})', False),
        ("series_sum(['host', 'dc'], {a='b'})", False),
        ('series_sum({a="b"}) + {c="d"}', False),
        ('series_sum({a="b"}', False),
        ('group_lines("sum", {a="b"})', True),
        ("group_lines('avg',{a='b'})", True),
        ('group_lines("sum", "host", {a="b"})', False),  # the deprecated form grouped by a label
        ('alias(series_sum({a="b", c="d"}), "cpu")', True),
        ('series_sum({a="b"}) / 1000', True),
        ('series_sum({a="b"}) / series_sum({c="d"})', False),
        ('alias({a="b"}, "cpu")', False),
    ],
)
def test_single_series(query, single):
    assert report.single_series(query) is single


@pytest.mark.parametrize(
    'query, function',
    [
        ('series_sum({a="b"})', 'sum'),
        ('alias(group_lines("sum", {a="b"}) * 1e-3, "x")', None),
        ('alias(group_lines("sum", {a="b"}) * 0.001, "x")', 'sum'),
        ('series_avg({a="b"})', 'avg'),
        ('series_max(series_sum({a="b"}))', 'max'),
    ],
)
def test_aggregation(query, function):
    assert report.aggregation(query) == function


MONIUM = {'query': 'series_sum({a="b"})', 'metric_type': 'cpu_usage', 'metric_name': 'pod.total/cores'}


@pytest.mark.parametrize(
    'sensors, metrics, problem',
    [
        ([{'query': 'series_sum({a="b"})', 'metric_type': 't', 'metric_name': 'n'}], ['custom:t_n'], None),
        ([], [], ('unsupported', 'no sensors')),
        (['{a="b"}'], [], ('unsupported', 'is a selector')),
        ([{'cluster': 'c', 'service': 's'}], [], ('unsupported', 'is a selector')),
        ([{'query': 'series_sum({a="b"})', 'metric_type': 't'}], [], ('unsupported', 'no explicit metric_type')),
        ([{'query': '{a="b"}', 'metric_type': 't', 'metric_name': 'n'}], [], ('unsupported', 'does not aggregate')),
        # the tank puts '-' for '/', '.', '_' of the type and for '/', '.' of the name
        ([MONIUM], ['custom:cpu-usage_pod-total-cores'], None),
        (
            [MONIUM],
            ['custom:cpu_usage_pod.total/cores'],
            ('error', 'its sensors give custom:cpu-usage_pod-total-cores'),
        ),
    ],
)
def test_solomon_problem(sensors, metrics, problem):
    found = report.solomon_problem(sensors, metrics)
    assert found is None if problem is None else (found[0] == problem[0] and problem[1] in found[1])


def test_target_cpu_from_its_source():
    rows = [(T + s + 0.1 * i, 'a', 1000, 0, 200) for s in range(60) for i in range(10)]
    points = {T + s: {'cpu': 1.5, 'throttled': 0.25} for s in range(0, 60, 5)}
    conf = {'source_id': 'h', 'usage_metric': 'cpu', 'throttled_metric': 'throttled', 'limit_cores': 4}
    specs = [spec(metrics=('cpu', 'throttled'), required=True)]
    doc = build(rows, pools([const(10, '60s')]), monitoring=specs, points={'h': points}, target_cpu=conf)
    assert doc['monitoring']['sources'][0]['status'] == 'ok'
    cpu = doc['target']['cpu']
    assert (cpu['source_id'], cpu['limit_cores']) == ('h', 4)
    assert cpu['windows'][0] == {
        'window': 'test',
        'usage_cores_mean': 1.5,
        'usage_cores_max': 1.5,
        'throttled_cores_mean': 0.25,
        'cpu_ms_per_req': 150.0,
    }
    assert [w['window'] for w in cpu['windows']] == [w['id'] for w in doc['windows']]
    # no target CPU when its source is empty or measures the generator
    doc = build(rows, pools([const(10, '60s')]), monitoring=specs, points={}, target_cpu=conf)
    assert (doc['target']['cpu'], doc['statuses']['completeness']['status']) == (None, 'INCOMPLETE')
    generator = [spec(metrics=('cpu',), entity='generator')]
    doc = build(rows, pools([const(10, '60s')]), monitoring=generator, points={'h': points}, target_cpu=conf)
    assert doc['target']['cpu'] is None


def test_target_cpu_per_request_up_to_its_last_point():
    """On a rising load CPU points end before E: CPU per request divides by the rps of the seconds they reach, so
    10 ms a request stays 10 ms (by the rps of the whole window it would be about 6)."""
    rps = [1 + s // 2 for s in range(150)]
    rows = [(T + s + (i + 0.5) / n, 'a', 1000, 0, 200) for s, n in enumerate(rps) for i in range(n)]
    points = {T + t: {'cpu': 0.01 * rps[t]} for t in range(0, 91, 15)}
    conf = {'source_id': 'h', 'usage_metric': 'cpu'}
    monitoring = [spec(metrics=('cpu',))]
    doc = build(rows, pools([line(1, 75, '150s')]), monitoring=monitoring, points={'h': points}, target_cpu=conf)
    test = doc['target']['cpu']['windows'][0]
    assert test['window'] == 'test' and test['cpu_ms_per_req'] == pytest.approx(10, rel=0.02)


@functools.lru_cache(maxsize=None)
def ramp_seconds():
    """Seconds and hist lines of a test window [T, T + 600), a response a second: aggregated once for all cases."""
    return summarize(aggregate([[phout((T + s + 0.5, 'a', 1000, 0, 200) for s in range(600))]]))


def ramp_cpu(ts, option=True, tolerance=60, values=None):
    """target.cpu of a 600 s ramp with usage points at T + ts (the value is ts / 1000 unless values {ts: value} give
    it), checked by the schema and the copy of report.Validate."""
    conf = {'source_id': 'h', 'usage_metric': 'cpu', 'series': option}
    if option is None:
        del conf['series']
    points = {T + t: {'cpu': (values or {}).get(t, t / 1000)} for t in ts}
    ctx = context(
        pools([line(1000, 12000, '600s')]),
        monitoring=[spec(metrics=('cpu',))],
        points={'h': points},
        target_cpu=conf,
        tolerance_s=tolerance,
    )
    doc = report.build(*ramp_seconds(), ctx)
    assert (window(doc, 'test')['start_ts'], window(doc, 'test')['end_ts']) == (T, T + 600)
    assert not errors(validator('machine_report'), 'machine_report', doc)
    return doc['target']['cpu']


@pytest.mark.parametrize('option', [None, False])
def test_target_cpu_series_off(option):
    assert 'series' not in ramp_cpu(range(7, 600, 15), option)


@pytest.mark.parametrize(
    'ts, tolerance, status',
    [
        # Monium points mid-step over the whole window but the last 40 s: late points within the tolerance
        (range(7, 560, 15), 60, 'ok'),
        # 45 s between neighbours at a 15 s step
        ([t for t in range(7, 600, 15) if t not in (202, 217)], 60, 'partial'),
        # the left edge as for a monitoring source: from S to the first point at most two steps
        (range(30, 600, 15), 60, 'ok'),
        (range(31, 600, 15), 60, 'partial'),
        # the right edge: the last point at most a step before E - tolerance, unless the tolerance is wider
        (range(0, 526, 15), 60, 'ok'),
        (range(7, 470, 15), 60, 'partial'),
        (range(7, 470, 15), 150, 'ok'),
        # a point after missing ones makes them a gap, in the tolerance too: they are lost, not late
        ([t for t in range(7, 600, 15) if t not in (547, 562, 577)], 60, 'partial'),
        # a test shorter than the tolerance: all its points may be late
        (range(307, 600, 15), 700, 'ok'),
    ],
)
def test_target_cpu_series(ts, tolerance, status):
    series = ramp_cpu(ts, tolerance=tolerance)['series']
    assert (series['status'], series['step_s']) == (status, 15) and 'reason' not in series
    assert series['points'] == [{'ts': T + t, 'cores': t / 1000} for t in ts]


def test_target_cpu_series_points_as_delivered():
    """Points out of the test window are dropped; Solomon ts are floats, written as integer seconds, and the later
    point of one second wins: the series stays at most one point a step."""
    series = ramp_cpu([-3, 600, 22.75] + [float(t) for t in range(7, 600, 15)])['series']
    assert (series['status'], series['step_s']) == ('ok', 15)
    expected = [{'ts': T + t, 'cores': (22.75 if t == 22 else t) / 1000} for t in range(7, 600, 15)]
    assert series['points'] == expected and all(type(p['ts']) is int for p in series['points'])


@pytest.mark.parametrize('bad', [-0.1, float('nan'), float('inf')])
def test_target_cpu_series_skips_what_is_no_cpu(bad):
    """A negative usage (a counter reset) is no CPU and the schema keeps cores from 0, NaN and inf are no numbers:
    the series has no point there, and that is a gap."""
    series = ramp_cpu(range(7, 560, 15), values={202: bad})['series']
    assert (series['status'], series['step_s']) == ('partial', 15)
    assert [p['ts'] for p in series['points']] == [T + t for t in range(7, 560, 15) if t != 202]


@pytest.mark.parametrize('ts, values', [([300], None), ([300, 315], {315: -0.5})])
def test_target_cpu_series_one_point(ts, values):
    series = ramp_cpu(ts, values=values)['series']
    assert series == {
        'status': 'unavailable',
        'reason': 'fewer than two points in the test window, the step is unknown',
        'step_s': None,
        'points': [],
    }


# Generator CPU

PID = os.getpid()
CGROUP_V1 = {
    # a tasklet: cpu,cpuacct mounted for the container, its own counters at the root
    'cpu/cpu.cfs_quota_us': '200000\n',
    'cpu/cpu.cfs_period_us': '100000\n',
    'cpu/cpu.stat': 'nr_periods 2246\nnr_throttled 31\nthrottled_time 1520000000\nh_throttled_time 0\nburst_usage 0\n',
    'cpuacct/cpuacct.usage': '4923062278080\n',
    'cpuacct/cgroup.procs': '1\n{}\n'.format(PID),
}
# /proc/self/cgroup of the tasklet (dev runs of LOAD-3806): the own cgroup at the root of every mount
TASKLET = '11:pids:/\n9:cpu,cpuacct:/\n1:name=systemd:/\n0::/\n'
CGROUP_V2 = {
    'cgroup.controllers': 'cpuset cpu io memory pids\n',
    'cgroup.procs': '{}\n'.format(PID),
    'cpu.max': '200000 100000\n',
    'cpu.stat': 'usage_usec 4923062278\nuser_usec 4100000000\nsystem_usec 823062278\n'
    'nr_periods 2246\nnr_throttled 31\nthrottled_usec 1520000\nnr_bursts 0\nburst_usec 0\n',
}


def cgroup(root, files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return str(root)


def tank_cgroup(tmp_path, files, lines='0::/\n'):
    """(mount root, /proc/self/cgroup) of a cgroup mount with files."""
    proc = tmp_path / 'proc-self-cgroup'
    proc.write_text(lines)
    return cgroup(tmp_path / 'cgroup', files), str(proc)


def read_cgroup(tmp_path, files, lines='0::/\n'):
    found, why = report.find_cgroup(*tank_cgroup(tmp_path, files, lines), PID)
    return (found, why) if found is None else (found, report.cgroup_cpu(found))


@pytest.mark.parametrize(
    'files, lines, expected',
    [
        (CGROUP_V1, TASKLET, ('cgroup_v1', 2.0, [4923.06227808, 1.52, 2246, 31])),
        (CGROUP_V2, '0::/\n', ('cgroup_v2', 2.0, [4923.062278, 1.52, 2246, 31])),
        # the cpu controller not delegated: usage without throttling, and no quota
        (
            {'cgroup.controllers': '', 'cgroup.procs': str(PID), 'cpu.stat': 'usage_usec 5000000\n'},
            '0::/\n',
            ('cgroup_v2', None, [5.0, None, None, None]),
        ),
        (dict(CGROUP_V1, **{'cpuacct/cpuacct.usage': 'garbage\n'}), TASKLET, ('cgroup_v1', 2.0, None)),
    ],
)
def test_cgroup_cpu(tmp_path, files, lines, expected):
    found, counters = read_cgroup(tmp_path, files, lines)
    assert (found.source, found.limit) == expected[:2]
    assert counters is None if expected[2] is None else list(counters) == pytest.approx(expected[2])


def test_cgroup_not_the_tank_one(tmp_path):
    """A mount that does not list the tank process is not its cgroup: a host mount would pass the CPU of the host."""
    found, why = read_cgroup(tmp_path, dict(CGROUP_V2, **{'cgroup.procs': '1\n'}))
    assert found is None and 'does not list the tank process' in why
    found, why = read_cgroup(tmp_path, CGROUP_V2, '')
    assert found is None and 'no cpu controller' in why


def test_cgroup_under_a_host_mount(tmp_path):
    """cgroup v2 of the host without a cgroup namespace: the own directory is found by /proc/self/cgroup, the quota
    is set on its parent, and throttling is counted there."""
    own = 'system.slice/tank.scope'
    files = {
        'cgroup.controllers': 'cpu\n',
        'cgroup.procs': '1\n',
        'cpu.stat': 'usage_usec 999000000\n',
        'system.slice/cpu.max': '100000 100000\n',
        'system.slice/cpu.stat': 'usage_usec 9000000\nnr_periods 100\nnr_throttled 7\nthrottled_usec 300000\n',
        own + '/cgroup.procs': '{}\n'.format(PID),
        own + '/cpu.max': 'max 100000\n',
        own + '/cpu.stat': 'usage_usec 2000000\nnr_periods 0\nnr_throttled 0\nthrottled_usec 0\n',
    }
    found, counters = read_cgroup(tmp_path, files, '0::/' + own + '\n')
    assert (found.source, found.limit) == ('cgroup_v2', 1.0)
    assert found.usage.endswith(own) and found.throttling.endswith('system.slice')
    assert list(counters) == pytest.approx([2.0, 0.3, 100, 7])


def test_generator_cpu_by_windows():
    # 1.5 cores, 0.1 s throttled per second, 10 CFS periods per second with 3 throttled; snapshots over [5, 25]
    snapshots = [(t + 0.5 * (t % 2), 1.5 * t, 0.1 * t, 10 * t, 3 * t) for t in range(5, 26)]
    windows = [report._Window('test', 'test', None, 0, 30), report._Window('steady-0', 'steady', 0, 10, 20)]
    cpu = report.generator_cpu('cgroup_v1', sorted(snapshots), 2, windows)
    assert cpu['source'] == 'cgroup_v1'
    test, steady = cpu['windows']
    assert test['window'] == 'test' and steady['window'] == 'steady-0'
    for w in (test, steady):
        assert w['usage_cores_mean'] == pytest.approx(1.5)
        assert w['util_pct_mean'] == pytest.approx(75)
        assert w['throttled_periods_pct'] == pytest.approx(30)
        assert w['throttled_cores_mean'] == pytest.approx(0.1)
    assert steady['throttled_s'] == pytest.approx(1.0)
    assert test['usage_cores_max'] >= 1.5 and test['util_pct_max'] == pytest.approx(test['usage_cores_max'] * 50)
    assert report.generator_cpu('unavailable', snapshots, 2, windows) == {'source': 'unavailable', 'windows': []}
    # a window without snapshots and counters without a quota
    empty = report.generator_cpu('cgroup_v2', [(0, 0, 0, 0, 0), (1, 1, 0, 0, 0)], 2, windows[1:])['windows'][0]
    assert empty['usage_cores_mean'] is None and empty['throttled_periods_pct'] is None


def test_generator_cpu_split_at_window_edges():
    """Snapshots off the window edges: an interval adds to a window by its overlap; 1 core up to 15.5 s, then 2."""
    snapshots = [(t + 0.5, t + 0.5 if t < 15 else 2 * t - 14.5, 0, 0, 0) for t in range(5, 25)]
    windows = [report._Window('steady-0', 'steady', 0, 10, 20)]
    [steady] = report.generator_cpu('cgroup_v2', snapshots, 2, windows)['windows']
    assert steady['usage_cores_mean'] == pytest.approx(1.45)


def test_generator_cpu_without_throttling_counters():
    snapshots = [(t, 1.5 * t, None, None, None) for t in range(30)]
    [test] = report.generator_cpu('cgroup_v2', snapshots, 2, [report._Window('test', 'test', None, 0, 30)])['windows']
    assert test['usage_cores_mean'] == pytest.approx(1.5)
    assert (test['throttled_s'], test['throttled_cores_mean'], test['throttled_periods_pct']) == (None, None, None)


# Saturation

THRESHOLDS = {
    'cpu_util_pct': 90,
    'cpu_throttled_periods_pct': 5,
    'discarded_shots_pct': 1,
    'plan_deficit_pct': 5,
    'sustain_s': 60,
}


def signals(doc):
    return {
        (s['code'], s['window']): (s['value'], s['unit'], s['threshold'])
        for s in doc['generator']['saturation']['signals']
    }


def test_saturation_signals():
    schedule = pools([const(10, '40s')])  # startup once(10): 10 instances
    rows = [(T + s + 0.1 * i, 'a', 1000, 0, 200) for s in range(40) for i in range(10)]
    data = aggregate([[phout(rows)]])
    seconds, lines = summarize(data, instances=5)
    doc = report.build(seconds, lines, context(schedule))
    assert doc['generator']['saturation'] == {'status': 'not_saturated', 'signals': []}

    # all instances busy (seconds without instances skipped), 95 % of 2 cores, 60 % of periods throttled
    seconds, lines = summarize(data, instances=10)
    seconds[3]['instances'] = None
    snapshots = [(T + t, 1.9 * t, 0.5 * t, 10 * t, 6 * t) for t in range(41)]
    cpu = {'source': 'cgroup_v2', 'snapshots': snapshots}
    doc = report.build(
        seconds, lines, context(schedule, cpu=cpu, generator=dict(context(schedule)['generator'], cores=2))
    )
    assert doc['generator']['saturation']['status'] == 'saturated'
    found = signals(doc)
    assert set(found) == {
        (code, w) for code in ('INSTANCES_EXHAUSTED', 'CPU_UTIL_HIGH', 'CPU_THROTTLED') for w in ('test', 'steady-0')
    }
    assert found['INSTANCES_EXHAUSTED', 'test'] == (10, 'count', 10)
    assert found['CPU_UTIL_HIGH', 'steady-0'] == (pytest.approx(95), 'pct', 90)
    assert found['CPU_THROTTLED', 'test'] == (pytest.approx(60), 'pct', 5)

    # shots discarded for want of instances: the plan is not met
    rows = [(T + s + 0.1 * i, 'a', 1000, 0, 200) for s in range(40) for i in range(5)]
    rows += [(T + s + 0.1 * i + 0.05, 'discarded', 0, 777, 0) for s in range(40) for i in range(5)]
    seconds, lines = summarize(aggregate([[phout(rows)]]), instances=0)  # expvar off: instances unknown
    doc = report.build(seconds, lines, context(schedule))
    assert {code for code, _ in signals(doc)} == {'DISCARDED_SHOTS', 'PLAN_NOT_MET'}
    assert signals(doc)['DISCARDED_SHOTS', 'test'] == (50, 'pct', 1)
    assert signals(doc)['PLAN_NOT_MET', 'steady-0'] == (50, 'pct', 5)
    assert all(s['instances'] is None for s in doc['load']['per_second'])


def test_saturation_unknown_without_data():
    assert report.saturation(THRESHOLDS, [], 1, [], [], []) == {'status': 'unknown', 'signals': []}


def const_run(instances=5):
    """Seconds and hist lines of 10 rps for 150 s."""
    rows = [(T + s + 0.1 * i, 'a', 1000, 0, 200) for s in range(150) for i in range(10)]
    return summarize(aggregate([[phout(rows)]]), instances=instances)


def test_saturation_at_the_end_of_the_window():
    """The generator runs out of CPU in the last 60 s: 54 % of the quota on average, 98 % sustained."""
    seconds, lines = const_run()
    usage = lambda t: 0.5 * t if t <= 90 else 45 + 1.96 * (t - 90)  # noqa: E731
    cpu = {'source': 'cgroup_v2', 'snapshots': [(T + t, usage(t), 0, 0, 0) for t in range(151)]}
    generator = dict(context([])['generator'], cores=2)
    doc = report.build(seconds, lines, context(pools([const(10, '150s')]), cpu=cpu, generator=generator))
    assert doc['generator']['cpu']['windows'][0]['util_pct_mean'] == pytest.approx(54.2)
    assert signals(doc) == {('CPU_UTIL_HIGH', 'test'): (pytest.approx(98), 'pct', 90)}


def test_instances_exhausted_held_for_sustain_s():
    """All 10 instances busy in one second is a pause of the target, 60 s in a row is the generator."""
    schedule = pools([const(10, '150s')])
    seconds, lines = const_run()
    seconds[40]['instances'] = 10
    doc = report.build(seconds, lines, context(schedule))
    assert doc['generator']['saturation'] == {'status': 'not_saturated', 'signals': []}
    for s in seconds[40:101]:
        s['instances'] = 10
    seconds[70]['instances'] = None  # unknown seconds are skipped
    doc = report.build(seconds, lines, context(schedule))
    assert signals(doc) == {('INSTANCES_EXHAUSTED', w): (10, 'count', 10) for w in ('test', 'steady-0')}
