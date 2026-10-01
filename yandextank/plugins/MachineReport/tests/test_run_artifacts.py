"""Files of one run as the plugin publishes them: report.json, hist.v1.jsonl.gz and the phout they were built from.

By default the anonymized files of a real pandora run (fixtures/run). MACHINE_REPORT, MACHINE_REPORT_HIST and
MACHINE_REPORT_PHOUT point the checks at downloaded files; check_run_artifacts.sh sets them and also runs the Go
report.Validate (load/projects/ai_analysis/report) on the same files."""

import gzip
import json
import math
import os
import re

import numpy as np
import pytest

from yandextank.plugins.MachineReport import report
from yandextank.plugins.Phantom.reader import string_to_df

from test_report import aggregate, assert_windows_match_phout, context, summarize
from test_schema import errors, source, validator

STEP = re.compile(r'^(\w+)\((.*)\)$')


def path(env, name):
    return os.environ.get(env) or source('tests', 'fixtures', 'run', name)


def read_text(name):
    with gzip.open(name, 'rt') if name.endswith('.gz') else open(name) as f:
        return f.read()


@pytest.fixture(scope='module')
def doc():
    return json.loads(read_text(path('MACHINE_REPORT', report.REPORT_FILE)))


@pytest.fixture(scope='module')
def hist_lines():
    return [json.loads(line) for line in read_text(path('MACHINE_REPORT_HIST', report.HIST_FILE)).splitlines()]


def test_report_valid(doc):
    assert not errors(validator('machine_report'), 'machine_report', doc)


def test_hist_valid_and_described_by_report(doc, hist_lines):
    v = validator('hist')
    for line in hist_lines:
        assert not errors(v, 'hist', line), line
    name = path('MACHINE_REPORT_HIST', report.HIST_FILE)
    assert doc['artifacts']['histograms'] == {
        'path': report.HIST_FILE,
        'format': 'hist.v1',
        'sha256': report.file_sha256(name),
        'bytes': os.path.getsize(name),
        'lines': len(hist_lines),
    }


def test_windows_from_hist(doc, hist_lines):
    """Quantiles of every window and case again from the hist file alone, as a consumer of the two files does."""
    for w in doc['windows']:
        lines = [li for li in hist_lines if w['start_ts'] <= li['ts'] < w['end_ts']]
        assert {li['case'] for li in lines} <= {None} | set(w['cases']), w['id']
        for case, agg in [(None, w)] + sorted(w['cases'].items()):
            counts, overflow = np.zeros(len(report.GRID), dtype=np.int64), 0
            for li in lines:
                if li['case'] == case:
                    counts[[report.GRID_INDEX[edge] for edge in li['upper_us']]] += li['counts']
                    overflow += li['overflow']
            where = (w['id'], case)
            assert int(counts.sum()) + overflow == agg['responses'], where
            assert overflow == agg['latency_overflow'], where
            assert report.latency_ms(counts, overflow, agg['responses']) == agg['latency_ms'], where


def schedule(texts):
    """Normalized load_profile steps (const(120,180s)) back to pandora schedule steps."""
    steps = []
    for text in texts:
        kind, args = STEP.match(text).groups()
        values = [a if a.endswith('s') else float(a) for a in args.split(',')]
        steps.append(dict(zip(report._STEP_ARGS[kind], values), type=kind))
    return steps


def replayed_pools(doc):
    return report.pandora_pools(
        [
            {'gun': {'type': p['gun']}, 'rps': schedule(p['schedule']), 'startup': schedule(p['startup'])}
            for p in doc['provenance']['load_profile']['pools']
        ]
    )


def trim_s(doc):
    """steady_trim_s of the run, read back from a steady window; the section default without one."""
    start = next(w['start_ts'] for w in doc['windows'] if w['kind'] == 'test')
    offsets = {p['index']: p['start_offset_s'] for p in doc['phases']}
    for w in doc['windows']:
        if w['kind'] == 'steady':
            return w['start_ts'] - start - math.ceil(offsets[w['phase_index']])
    return 15


def test_replay_equals_report(doc):
    """The run's own phout through the tank aggregation and report.build gives the same phases, windows and
    seconds (instances come from pandora expvar, the phout has none). One pool: a phout per pool otherwise."""
    if os.environ.get('MACHINE_REPORT') and not os.environ.get('MACHINE_REPORT_PHOUT'):
        pytest.skip('no phout for the downloaded run')
    text = read_text(path('MACHINE_REPORT_PHOUT', 'phout.log.gz'))
    rows = text.splitlines(True)
    seconds, lines = summarize(aggregate([[''.join(rows[i : i + 1000]) for i in range(0, len(rows), 1000)]]))
    replay = report.build(seconds, lines, context(replayed_pools(doc), trim_s=trim_s(doc)))
    assert replay['phases'] == doc['phases']
    assert replay['windows'] == doc['windows']

    def second(s):
        return {k: v for k, v in s.items() if k != 'instances'}

    assert [second(s) for s in replay['load']['per_second']] == [second(s) for s in doc['load']['per_second']]
    assert_windows_match_phout(doc, string_to_df(text))
