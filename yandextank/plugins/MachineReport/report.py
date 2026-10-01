"""Pure part of the MachineReport plugin: the load profile of the generator, per-second summaries of the tank
aggregator and the report built from them (machine_report.v1 and hist.v1 in schema/). Nothing here touches the
tank core, so tests drive it without TankCore."""

import gzip
import hashlib
import json
import math
import os
import re
import subprocess
from collections import Counter, defaultdict, namedtuple
from decimal import Decimal
from fractions import Fraction

import numpy as np

from yandextank.aggregator.aggregator import Worker

SCHEMA_VERSION = 'machine_report.v1'
PLUGIN_VERSION = '0.1.0'
REPORT_FILE = 'report.json'
HIST_FILE = 'hist.v1.jsonl.gz'
DISCARDED_TAG = 'discarded'
DISCARDED_CODE = '777'
# pandora tags a shot without a tag (and an invalid ammo) with it: not a case of its own
EMPTY_TAG = '__EMPTY__'
# responses may come this long after the schedule ends; a wider span of data seconds is a stray timestamp
MAX_TAIL_S = 3600
QUANTILES = ('50', '75', '90', '95', '98', '99', '100')
# Upper edges of the verbose histogram grid of the tank aggregator, microseconds.
GRID = [int(round(edge)) for edge in Worker({}, True).bins[1:]]
GRID_INDEX = {edge: i for i, edge in enumerate(GRID)}
PROFILE_STRING = re.compile(r'^[A-Za-z0-9_.,:/()+*-]+$')


class NoReport(Exception):
    """A correct report cannot be built, so none is written; the reason goes to the log."""


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def json_sha256(value, ensure_ascii=True):
    text = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=ensure_ascii)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


# Load profile


_DURATION_UNITS = {
    'ns': Fraction(1, 10**9),
    'us': Fraction(1, 10**6),
    'µs': Fraction(1, 10**6),
    'μs': Fraction(1, 10**6),
    'ms': Fraction(1, 1000),
    's': Fraction(1),
    'm': Fraction(60),
    'h': Fraction(3600),
}
_DURATION_PART = re.compile(r'(\d+(?:\.\d*)?|\.\d+)(ns|us|µs|μs|ms|s|m|h)')


def parse_duration(value):
    """Go duration string of a pandora schedule (1m30s, 300ms) to exact seconds."""
    if not isinstance(value, str):
        raise ValueError('duration {!r} is not a string'.format(value))
    text = value.strip()
    if text == '0':
        return Fraction(0)
    total, pos = Fraction(0), 0
    for m in _DURATION_PART.finditer(text):
        if m.start() != pos:
            break
        total += Fraction(m.group(1)) * _DURATION_UNITS[m.group(2)]
        pos = m.end()
    if pos == 0 or pos != len(text):
        raise ValueError('bad duration {!r}'.format(value))
    return total


def exact(value):
    """Config number to an exact fraction; a float by its shortest decimal form (0.1 is 1/10)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('{!r} is not a number'.format(value))
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('{!r} is not a number'.format(value))
        return Fraction(repr(value))
    return Fraction(value)


def decimal_text(value):
    """Shortest decimal form without exponent and trailing zeros of a decimal fraction."""
    return format((Decimal(value.numerator) / Decimal(value.denominator)).normalize(), 'f')


def json_number(value):
    return int(value) if value.denominator == 1 else float(value)


_STEP_ARGS = {
    'const': ('ops', 'duration'),
    'line': ('from', 'to', 'duration'),
    'step': ('from', 'to', 'step', 'duration'),
    'once': ('times',),
    'unlimited': ('duration',),
    'instance_step': ('from', 'to', 'step', 'stepduration'),
}
_DURATION_ARGS = ('duration', 'stepduration')
RPS_STEPS = ('const', 'line', 'step', 'once', 'unlimited')


def parse_steps(schedule, allowed=tuple(_STEP_ARGS)):
    """Pandora schedule (a step or a list of steps) to [(type, {arg: Fraction}, normalized text)]."""
    steps = schedule if isinstance(schedule, list) else [schedule]
    out = []
    for step in steps:
        if not isinstance(step, dict):
            raise ValueError('schedule step {!r} is not a mapping'.format(step))
        conf = {str(k).lower(): v for k, v in step.items()}
        kind = str(conf.get('type', '')).lower()
        if kind not in allowed:
            raise NoReport('schedule step type {!r} is not supported'.format(conf.get('type')))
        args, texts = {}, []
        for name in _STEP_ARGS[kind]:
            if name not in conf:
                raise ValueError('schedule step {} has no {}'.format(kind, name))
            if name in _DURATION_ARGS:
                args[name] = parse_duration(conf[name])
                texts.append(decimal_text(args[name]) + 's')
            else:
                args[name] = exact(conf[name])
                texts.append(decimal_text(args[name]))
        out.append((kind, args, '{}({})'.format(kind, ','.join(texts))))
    return out


# kind, start and duration in seconds of the schedule; from_rps and to_rps; segments: [(t0, t1, rate0, rate1)]
# of a linear rate relative to start, None when the rate is unknown (unlimited); impulses: [(t, shots)].
Phase = namedtuple('Phase', 'kind start duration from_rps to_rps segments impulses')


def _phase(kind, args, start):
    if kind == 'const':
        rate, duration = args['ops'], args['duration']
        return Phase(kind, start, duration, rate, rate, [(0, duration, rate, rate)], [])
    if kind == 'line':
        duration = args['duration']
        return Phase(kind, start, duration, args['from'], args['to'], [(0, duration, args['from'], args['to'])], [])
    if kind == 'step':
        # as pandora NewStep: const levels from, from + step, ... <= to; none at all when from > to
        low, high, step, duration = args['from'], args['to'], args['step'], args['duration']
        levels = [low] if low == high else [low + i * step for i in range(int((high - low) // step) + 1)]
        segments = [(i * duration, (i + 1) * duration, level, level) for i, level in enumerate(levels)]
        return Phase(kind, start, len(levels) * duration, low, levels[-1] if levels else low, segments, [])
    if kind == 'once':
        return Phase(kind, start, Fraction(0), args['times'], args['times'], [], [(0, args['times'])])
    return Phase(kind, start, args['duration'], None, None, None, [])  # unlimited


def _segment_shots(t0, t1, r0, r1):
    """(first, last, widest gap) of the shots of one pandora const or line schedule, seconds; None without shots.
    As pandora core/schedule: n = int(planned shots), shot i at the root of the cumulative plan, i / r for const."""
    n = math.floor((r0 + r1) * (t1 - t0) / 2)
    if n < 1:
        return None
    if r0 == r1:
        at = lambda i: t0 + i / r0  # noqa: E731
    else:
        a = (r1 - r0) / (t1 - t0)
        at = lambda i: t0 + (math.sqrt(2 * a * i + r0 * r0) - r0) / a  # noqa: E731
    gap = 0 if n == 1 else max(at(1) - at(0), at(n - 1) - at(n - 2))
    return t0, at(n - 1), gap


def _phase_shots(phase):
    """[(first, last, widest gap)] of the shots of a phase from the schedule start; unlimited shoots all along."""
    if phase.segments is None:
        return [(phase.start, phase.start + phase.duration, 0)]
    shots = [(phase.start + t, phase.start + t, 0) for t, n in phase.impulses if n >= 1]
    for t0, t1, r0, r1 in phase.segments:
        segment = _segment_shots(phase.start + t0, phase.start + t1, r0, r1)
        if segment:
            shots.append(segment)
    return shots


def _startup_instances(steps):
    """Instances a pandora startup schedule starts: known for once and instance_step only."""
    total = 0
    for kind, args, _ in steps:
        if kind == 'once':
            total += args['times']
        elif kind == 'instance_step':
            low, high, step = args['from'], args['to'], args['step']
            total += low + step * len(range(int(low + step), int(high) + 1, int(step)))
        else:
            return None
    return int(total) if total >= 1 else None


def _profile_string(value, what):
    value = str(value)
    if not PROFILE_STRING.match(value):
        raise NoReport('{} {!r} is not expressible in load_profile'.format(what, value))
    return value


def _transport(gun_type, tls):
    if gun_type in ('http', 'http/scenario', 'connect'):
        return ('http1_tls' if tls else 'http1'), 'http'
    if gun_type in ('http2', 'http2/scenario'):
        # h2c is the gRPC setup of the main customer: taking it for HTTP would count errors by HTTP 200
        return ('h2', 'http') if tls else ('h2c', 'grpc')
    if gun_type in ('grpc', 'grpc/scenario'):
        return ('h2' if tls else 'h2c'), 'grpc'
    return 'other', 'other'


class Pool(object):
    def __init__(self, profile, phases, grpc_by_default=False):
        self.profile = profile
        self.phases = phases
        # an HTTP/2 pool without TLS taken for gRPC over h2c without an override: the plugin warns about it
        self.grpc_by_default = grpc_by_default

    @classmethod
    def from_pandora(cls, pool, override=None):
        """A pool of the patched pandora config (ammo files are local paths there)."""
        # load_profile of v1 has no field for these, and a report would equate different loads
        if pool.get('rps-per-instance'):
            raise NoReport('rps-per-instance multiplies the schedule by the instances, load_profile cannot express it')
        if not pool.get('discard_overflow', True):
            raise NoReport(
                'discard_overflow: false delays shots instead of discarding them, load_profile cannot express it'
            )
        gun = pool.get('gun') or {}
        gun_type = _profile_string(gun.get('type', ''), 'gun')
        transport, protocol = _transport(gun_type, bool(gun.get('ssl') or gun.get('tls')))
        override = (override or {}).get('target_protocol')
        ammo = pool.get('ammo') or {}
        if ammo.get('file'):
            ammo_sha256 = file_sha256(ammo['file'])
        elif ammo.get('uris'):
            ammo_sha256 = json_sha256(ammo['uris'], ensure_ascii=False)
        else:
            ammo_sha256 = None
        rps = parse_steps(pool['rps'], RPS_STEPS)
        startup = parse_steps(pool.get('startup') or [])
        phases, start = [], Fraction(0)
        for kind, args, _ in rps:
            phases.append(_phase(kind, args, start))
            start += phases[-1].duration
        profile = {
            'gun': gun_type,
            'transport': transport,
            'target_protocol': override or protocol,
            'load_type': 'rps',
            'schedule': [text for _, _, text in rps],
            'startup': [text for _, _, text in startup],
            'instances': _startup_instances(startup),
            'ammo_type': _profile_string(ammo['type'], 'ammo type') if ammo.get('type') else None,
            'ammo_sha256': ammo_sha256,
        }
        return cls(profile, phases, transport == 'h2c' and gun_type.startswith('http2') and not override)

    @property
    def first_shot(self):
        """Seconds from the schedule start to the first planned shot; None when the pool plans none."""
        shots = [s for phase in self.phases for s in _phase_shots(phase)]
        return shots[0][0] if shots else None

    @property
    def silence(self):
        """The longest planned time between two shots of the pool, seconds. Before the first shot the pool has not
        started, after the last one it has finished: neither is a silence."""
        longest, last = 0, None
        for first, end, gap in (s for phase in self.phases for s in _phase_shots(phase)):
            longest = max(longest, gap, 0 if last is None else first - last)
            last = end
        return longest

    def plan(self):
        """Planned shots per second of the schedule, {second: Fraction}; None for a second with an unknown plan."""
        plan = defaultdict(Fraction)
        for phase in self.phases:
            if phase.segments is None:
                for second in range(math.floor(phase.start), math.ceil(phase.start + phase.duration)):
                    plan[second] = None
                continue
            for t, shots in phase.impulses:
                second = math.floor(phase.start + t)
                if plan[second] is not None:
                    plan[second] += shots
            for t0, t1, r0, r1 in phase.segments:
                a, b = phase.start + t0, phase.start + t1
                if a == b:
                    continue
                rate = lambda u: r0 + (r1 - r0) * (u - a) / (b - a)  # noqa: E731
                for second in range(math.floor(a), math.ceil(b)):
                    u0, u1 = max(a, second), min(b, second + 1)
                    if u0 < u1 and plan[second] is not None:
                        plan[second] += (u1 - u0) * (rate(u0) + rate(u1)) / 2
        return plan


def pandora_pools(pools, overrides=()):
    if not pools:
        raise ValueError('pandora config has no pools')
    overrides = list(overrides or [])
    return [Pool.from_pandora(pool, overrides[i] if i < len(overrides) else None) for i, pool in enumerate(pools)]


def check_pauses(pools, max_wait):
    """The tank aggregator drops a pool source silent for core.aggregator_max_wait after its first data until the end
    of the shooting; the silence before the first data does not count."""
    for i, pool in enumerate(pools):
        if pool.silence >= max_wait:
            raise NoReport(
                'pool {} plans {:.1f} s without shots, not shorter than core.aggregator_max_wait {} s: the '
                'aggregator drops the pool after such a silence'.format(i, float(pool.silence), max_wait)
            )


def grpc_status(pools):
    """Weakest over gRPC pools: not_read over http_mapped. Pandora grpc guns map statuses to HTTP-like codes."""
    statuses = [
        'http_mapped' if p.profile['gun'] in ('grpc', 'grpc/scenario') else 'not_read'
        for p in pools
        if p.profile['target_protocol'] == 'grpc'
    ]
    if not statuses:
        return 'not_applicable'
    return 'not_read' if 'not_read' in statuses else 'http_mapped'


def pandora_version(cmd, timeout=2):
    """Version from `pandora -version`: the build of pandorax (Pandora X - <version>), else Pandora core/<version>;
    None when it cannot be read."""
    try:
        result = subprocess.run([cmd, '-version'], capture_output=True, text=True, timeout=timeout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    m = re.search(r'Pandora (?:X - |core/)(\S+)', (result.stderr or '') + (result.stdout or ''))
    return m.group(1) if m else None


# Config hash

_SECRET_NAME = re.compile(r'^(?:authorization|cookie)$|token|secret|password|passwd|oauth|ticket|key', re.I)
_HEADER = re.compile(r'^(\s*\[?\s*)([^:\[\]]+?)(\s*:\s*)(.*?)(\s*\]?\s*)$', re.S)
_QUERY_PARAM = re.compile(r'(?<=[?&;])([^=&;#\s]+)=([^&;#\s]*)')


def _mask_string(value):
    m = _HEADER.match(value)
    if m and _SECRET_NAME.search(m.group(2).strip()):
        value = m.group(1) + m.group(2) + m.group(3) + '***' + m.group(5)
    return _QUERY_PARAM.sub(lambda q: q.group(1) + '=***' if _SECRET_NAME.search(q.group(1)) else q.group(0), value)


def mask(node):
    """Masks values by name: config keys, 'Name: value' headers and URL query parameters."""
    if isinstance(node, dict):
        return {str(k): '***' if _SECRET_NAME.search(str(k)) else mask(v) for k, v in node.items()}
    if isinstance(node, (list, tuple)):
        return [mask(v) for v in node]
    if isinstance(node, str):
        return _mask_string(node)
    return node


def config_sha256(config):
    text = json.dumps(mask(config), sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


# Seconds of the aggregator


def _codes(count):
    return Counter({str(code): int(n) for code, n in (count or {}).items()})


def _hist(agg):
    hist = agg.get('hist') or {'bins': [], 'data': []}
    counts = Counter()
    for edge, n in zip(hist['bins'], hist['data']):
        edge = int(round(edge))
        if edge not in GRID_INDEX:
            raise ValueError('histogram edge {} is not on the verbose grid of the aggregator'.format(edge))
        counts[edge] += int(n)
    return counts


def _hist_line(ts, case, counts, responses):
    if any(n < 0 for n in counts.values()):
        raise ValueError('second {}: negative histogram count after removing discarded shots'.format(ts))
    upper = sorted(edge for edge, n in counts.items() if n > 0)
    counted = [counts[edge] for edge in upper]
    overflow = responses - sum(counted)
    if overflow < 0:
        raise ValueError('second {} case {}: histogram holds more than {} responses'.format(ts, case, responses))
    return {'ts': ts, 'case': case, 'upper_us': upper, 'counts': counted, 'overflow': overflow}


def summarize_second(data, stats):
    """One second of the aggregator to a compact summary and its hist.v1 lines. Shots tagged discarded (net code
    777) leave the responses, the protocol codes and the histograms; they stay in the net codes only."""
    ts = int(data['ts'])
    overall = data['overall']
    tagged = dict(data.get('tagged') or {})
    discarded = tagged.pop(DISCARDED_TAG, None)
    net = _codes(overall['net_code']['count'])
    http = _codes(overall['proto_code']['count'])
    counts = _hist(overall['interval_real'])
    dropped = 0
    if discarded is not None:
        stray = sorted(set(_codes(discarded['net_code']['count'])) - {DISCARDED_CODE})
        if stray:
            raise ValueError('second {}: shots tagged {} have net codes {}'.format(ts, DISCARDED_TAG, stray))
        dropped = int(discarded['interval_real']['len'])
        http.subtract(_codes(discarded['proto_code']['count']))
        counts.subtract(_hist(discarded['interval_real']))
    if net.get(DISCARDED_CODE, 0) != dropped:
        raise ValueError(
            'second {}: {} shots have net code {}, {} are tagged {}'.format(
                ts, net.get(DISCARDED_CODE, 0), DISCARDED_CODE, dropped, DISCARDED_TAG
            )
        )
    responses = int(overall['interval_real']['len']) - dropped
    lines = [_hist_line(ts, None, counts, responses)] if responses else []
    cases = {}
    tagged.pop(EMPTY_TAG, None)
    for tag, agg in sorted(tagged.items()):
        n = int(agg['interval_real']['len'])
        if n:
            lines.append(_hist_line(ts, str(tag), _hist(agg['interval_real']), n))
            cases[str(tag)] = {'responses': n, 'max_us': float(agg['interval_real']['max'])}
    instances = ((stats or {}).get('metrics') or {}).get('instances')
    summary = {
        'ts': ts,
        'responses': responses,
        # discarded shots have interval_real 0, so the overall max is the max of the responses
        'max_us': float(overall['interval_real']['max']) if responses else None,
        'net': dict(net),
        'http': {code: n for code, n in http.items() if n},
        # 0 also comes when the pandora expvar is unavailable, so it means unknown
        'instances': int(instances) if instances else None,
        'cases': cases,
    }
    return summary, lines


def _max(a, b):
    return b if a is None else a if b is None else max(a, b)


def merge_seconds(seconds):
    """Summaries by ts: a ts may come twice (the chopper yields late rows of a second again)."""
    merged = {}
    for s in seconds:
        m = merged.get(s['ts'])
        if m is None:
            merged[s['ts']] = dict(
                s,
                net=Counter(s['net']),
                http=Counter(s['http']),
                cases={tag: dict(c) for tag, c in s['cases'].items()},
            )
            continue
        m['responses'] += s['responses']
        m['max_us'] = _max(m['max_us'], s['max_us'])
        m['net'].update(s['net'])
        m['http'].update(s['http'])
        m['instances'] = _max(m['instances'], s['instances'])
        for tag, c in s['cases'].items():
            mc = m['cases'].setdefault(tag, {'responses': 0, 'max_us': None})
            mc['responses'] += c['responses']
            mc['max_us'] = _max(mc['max_us'], c['max_us'])
    return merged


def sorted_codes(codes):
    return {code: int(codes[code]) for code in sorted(codes, key=int) if codes[code]}


class HistWriter(object):
    """hist.v1.jsonl.gz written line by line during the shooting; mtime 0 keeps the bytes reproducible."""

    def __init__(self, path):
        self.path = path
        self._raw = open(path, 'wb')
        self._gz = gzip.GzipFile(filename='', mode='wb', fileobj=self._raw, mtime=0)
        self.lines = 0

    def write(self, lines):
        for line in lines:
            self._gz.write((json.dumps(line, separators=(',', ':')) + '\n').encode('utf-8'))
            self.lines += 1

    def close(self):
        if not self._raw.closed:
            self._gz.close()
            self._raw.close()

    def artifact(self):
        """artifacts.histograms of the report, by the final gzip bytes."""
        self.close()
        return {
            'path': HIST_FILE,
            'format': 'hist.v1',
            'sha256': file_sha256(self.path),
            'bytes': os.path.getsize(self.path),
            'lines': self.lines,
        }


def read_hist(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        for line in f:
            yield json.loads(line)


# Report


def latency_ms(counts, overflow, responses):
    """Nearest rank over merged histogram counts (per GRID bin): k = ceil(p * n / 100) exactly, the upper edge of
    the first bin reaching k in milliseconds, None when k falls into the overflow."""
    if not responses:
        return None
    cumulative = np.cumsum(counts)
    out = {}
    for p in QUANTILES:
        k = math.ceil(Fraction(p) * responses / 100)
        out['p' + p] = None if k > responses - overflow else GRID[int(np.searchsorted(cumulative, k))] / 1000
    return out


class _Window(object):
    def __init__(self, id, kind, phase_index, start, end):
        self.id, self.kind, self.phase_index, self.start, self.end = id, kind, phase_index, start, end
        self.responses, self.max_us = 0, None
        self.net, self.http = Counter(), Counter()
        self.cases = {}
        self.hist = {}
        self.overflow = Counter()

    def add_second(self, s):
        self.responses += s['responses']
        self.max_us = _max(self.max_us, s['max_us'])
        self.net.update(s['net'])
        self.http.update(s['http'])
        for tag, c in s['cases'].items():
            wc = self.cases.setdefault(tag, {'responses': 0, 'max_us': None})
            wc['responses'] += c['responses']
            wc['max_us'] = _max(wc['max_us'], c['max_us'])

    def add_line(self, case, bins, counts, overflow):
        hist = self.hist.get(case)
        if hist is None:
            hist = self.hist[case] = np.zeros(len(GRID), dtype=np.int64)
        hist[bins] += counts
        self.overflow[case] += overflow

    def _latency(self, case, responses, max_us):
        counts = self.hist.get(case)
        overflow = self.overflow[case]
        if (0 if counts is None else int(counts.sum())) + overflow != responses:
            raise ValueError(
                'window {} case {}: histograms do not hold its {} responses'.format(self.id, case, responses)
            )
        return {
            'latency_ms': latency_ms(counts, overflow, responses),
            'latency_max_ms': None if max_us is None else max_us / 1000,
            'latency_overflow': overflow,
        }

    def render(self):
        doc = {'id': self.id, 'kind': self.kind}
        if self.phase_index is not None:
            doc['phase_index'] = self.phase_index
        doc.update(
            start_ts=self.start,
            end_ts=self.end,
            responses=self.responses,
            rps_mean=self.responses / (self.end - self.start),
            **self._latency(None, self.responses, self.max_us),
        )
        doc['net_codes'] = sorted_codes(self.net)
        doc['http_codes'] = sorted_codes(self.http)
        doc['cases'] = {
            tag: dict(responses=c['responses'], **self._latency(tag, c['responses'], c['max_us']))
            for tag, c in sorted(self.cases.items())
        }
        return doc


def _windows(phases, start, end, trim):
    """[S, E) of the test, a phase-<n> window for every started phase, a steady-<n> one for a const phase."""
    windows = [_Window('test', 'test', None, start, end)]
    for index, (_, phase) in enumerate(phases):
        if start + phase.start < end:
            low = start + math.floor(phase.start)
            high = max(low + 1, min(end, start + math.ceil(phase.start + phase.duration)))
            windows.append(_Window('phase-{}'.format(index), 'phase', index, low, high))
        # a const(0) pause has no load to be steady in
        if phase.kind == 'const' and phase.from_rps > 0:
            low = start + math.ceil(phase.start) + trim
            high = min(end, start + math.floor(phase.start + phase.duration)) - trim
            if high - low >= 1:
                windows.append(_Window('steady-{}'.format(index), 'steady', index, low, high))
    return windows


def build(seconds, hist_lines, ctx):
    """The report from per-second summaries (in any order, a ts may repeat) and the hist.v1 lines written for
    them. ctx holds pools, trim_s and the sections the plugin knows before the shooting ends."""
    merged = merge_seconds(seconds)
    if not merged:
        raise NoReport('the aggregator delivered no seconds')
    pools = ctx['pools']
    first, last = min(merged), max(merged)
    # S: the schedule start is the first second with data minus the time to the first planned shot
    start = first - math.floor(min((p.first_shot for p in pools if p.first_shot is not None), default=0))
    end = last + 1
    duration = max(sum(phase.duration for phase in pool.phases) for pool in pools)
    if end - start > duration + MAX_TAIL_S:
        raise NoReport(
            'data seconds span {} s, the schedule {} s: a stray timestamp'.format(end - start, decimal_text(duration))
        )
    phases = [(i, phase) for i, pool in enumerate(pools) for phase in pool.phases]
    windows = _windows(phases, start, end, ctx['trim_s'])
    cover = defaultdict(list)
    for w in windows:
        for ts in range(w.start, w.end):
            cover[ts].append(w)
    for ts, s in merged.items():
        for w in cover[ts]:
            w.add_second(s)
    for line in hist_lines:
        covering = cover.get(int(line['ts']))
        if covering:
            bins = [GRID_INDEX[edge] for edge in line['upper_us']]
            counts = np.asarray(line['counts'], dtype=np.int64)
            for w in covering:
                w.add_line(line['case'], bins, counts, line['overflow'])

    plans = [pool.plan() for pool in pools]
    per_second = []
    for ts in range(start, end):
        planned = Fraction(0)
        for plan in plans:
            shots = plan.get(ts - start, 0)
            if shots is None:
                planned = None
                break
            planned += shots
        s = merged.get(ts)
        per_second.append(
            {
                'ts': ts,
                'rps': s['responses'] if s else 0,
                'planned_rps': None if planned is None else json_number(planned),
                'instances': s['instances'] if s else None,
                'net_codes': sorted_codes(s['net']) if s else {},
                'http_codes': sorted_codes(s['http']) if s else {},
            }
        )

    load_profile = {'pools': [pool.profile for pool in pools]}
    return {
        'schema_version': SCHEMA_VERSION,
        'provenance': dict(ctx['provenance'], load_profile_sha256=json_sha256(load_profile), load_profile=load_profile),
        'statuses': ctx['statuses'],
        'phases': [
            {
                'index': index,
                'pool': pool,
                'kind': phase.kind,
                'from_rps': None if phase.from_rps is None else json_number(phase.from_rps),
                'to_rps': None if phase.to_rps is None else json_number(phase.to_rps),
                'start_offset_s': json_number(phase.start),
                'duration_s': json_number(phase.duration),
            }
            for index, (pool, phase) in enumerate(phases)
        ],
        'windows': [w.render() for w in windows],
        'load': {
            'gun': dict(ctx['gun'], grpc_status=grpc_status(pools)),
            # pandora reports a protocol code of every response; the grpc gun maps gRPC statuses to HTTP-like codes
            'code_kinds': ['net', 'http'],
            'autostop_criteria': ctx['autostop_criteria'],
            'per_second': per_second,
        },
        'artifacts': {'histograms': ctx['histograms']},
        'monitoring': {'sources': ctx['monitoring']},
        'generator': ctx['generator'],
        'target': ctx['target'],
        'perforator': ctx['perforator'],
    }


def completeness(sources):
    blocking = [s['id'] for s in sources if s['required'] and s['status'] in ('empty', 'error', 'unsupported')]
    if blocking:
        return {'status': 'INCOMPLETE', 'blocking': True, 'blocking_sources': blocking}
    status = 'PARTIAL' if any(s['status'] != 'ok' for s in sources) else 'COMPLETE'
    return {'status': status, 'blocking': False, 'blocking_sources': []}


def generator_dc(dc, dc_env, environ):
    """The section dc, then the first set variable of dc_env up to the first dot (sas.<domain> gives sas)."""
    if dc:
        return dc
    for name in dc_env:
        head = (environ.get(name) or '').split('.', 1)[0]
        if head:
            return head
    return None


def cpu_model(path='/proc/cpuinfo'):
    try:
        with open(path) as f:
            for line in f:
                if line.startswith('model name'):
                    return line.split(':', 1)[1].strip() or None
    except OSError:
        pass
    return None
