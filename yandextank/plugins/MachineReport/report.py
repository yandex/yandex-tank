"""Pure part of the MachineReport plugin: the load profile of the generator, per-second summaries of the tank
aggregator and the report built from them (machine_report.v1 and hist.v1 in schema/). Nothing here touches the
tank core, so tests drive it without TankCore."""

import bisect
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
PLUGIN_VERSION = '0.2.0'
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
    """Instances a pandora startup schedule starts, one per its shot; None for unlimited."""
    total = 0
    for kind, args, _ in steps:
        if kind == 'instance_step':
            low, high, step = args['from'], args['to'], args['step']
            total += low + step * len(range(int(low + step), int(high) + 1, int(step)))
        elif kind == 'unlimited':
            return None
        else:
            phase = _phase(kind, args, 0)
            total += sum(n for _, n in phase.impulses)
            total += sum(math.floor((r0 + r1) * (t1 - t0) / 2) for t0, t1, r0, r1 in phase.segments)
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
    rendered = [w.render() for w in windows]
    sources = monitoring(ctx['monitoring'], ctx['points'], windows, start, end, ctx['tolerance_s'])
    capacity = ctx['generator'].get('cpu_limit_cores') or ctx['generator']['cores']
    snapshots = [] if ctx['cpu']['source'] == 'unavailable' else sorted(ctx['cpu']['snapshots'])
    cpu = generator_cpu(ctx['cpu']['source'], snapshots, capacity, windows)
    return {
        'schema_version': SCHEMA_VERSION,
        'provenance': dict(ctx['provenance'], load_profile_sha256=json_sha256(load_profile), load_profile=load_profile),
        'statuses': dict(ctx['statuses'], completeness=completeness(sources)),
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
        'windows': rendered,
        'load': {
            'gun': dict(ctx['gun'], grpc_status=grpc_status(pools)),
            # pandora reports a protocol code of every response; the grpc gun maps gRPC statuses to HTTP-like codes
            'code_kinds': ['net', 'http'],
            'autostop_criteria': ctx['autostop_criteria'],
            'per_second': per_second,
        },
        'artifacts': {'histograms': ctx['histograms']},
        'monitoring': {'sources': sources},
        'generator': dict(
            ctx['generator'],
            cpu=cpu,
            saturation=saturation(ctx['saturation'], snapshots, capacity, rendered, per_second, pools),
        ),
        'target': dict(
            ctx['target'],
            cpu=target_cpu(ctx['target_cpu'], sources, rendered, per_second, ctx['points'], ctx['tolerance_s']),
        ),
        'perforator': ctx['perforator'],
    }


# Monitoring

# both come through the tank Solomon plugin: the source host is the name of its panel
SOLOMON_KINDS = ('solomon', 'monium')
# yandextank.common.monitoring.convert_name cuts the metric names of these plugins to this length
CUT_KINDS = SOLOMON_KINDS + ('yc_monitoring',)
SOLOMON_NAME_LEN = 100
# an aggregation over all series; a quoted label or a label list before the selector groups by it and gives a series
# per value (group_lines with a label is the deprecated form of that)
_AGGREGATION = re.compile(r'\s*(?:series_(sum|avg|max|min)\s*\(|group_lines\s*\(\s*([\'"])(\w+)\2\s*,)\s*(?![\'"\[\s])')
# wrappers that keep one series one: alias(<query>, "name") and scaling by a number
_ALIAS = re.compile(r'\s*alias\s*\((.*),\s*([\'"]).*\2\s*\)\s*$', re.S)
_SCALED = re.compile(r'(.*?)\s*[*/]\s*\d+(?:\.\d*)?\s*$', re.S)


def data_name(kind, name):
    """Name of a section metric in tank monitoring data."""
    return name[:SOLOMON_NAME_LEN] if kind in CUT_KINDS else name


def aggregation(query):
    """The function of a Solomon query that aggregates all series into one: sum for series_sum(<selector>) and
    group_lines("sum", <selector>), also under alias(...) or scaled by a number; None for any other query."""
    m = _ALIAS.match(query) or _SCALED.match(query)
    if m:
        return aggregation(m.group(1))
    m = _AGGREGATION.match(query)
    if not m:
        return None
    depth, quote = 1, None
    for i in range(m.end(), len(query)):
        ch = query[i]
        if quote:
            quote = None if ch == quote else quote
        elif ch in '\'"':
            quote = ch
        elif ch in '()':
            depth += 1 if ch == '(' else -1
            if depth == 0:
                return None if query[i + 1 :].strip() else m.group(1) or m.group(3)
    return None


def single_series(query):
    return aggregation(query) is not None


def solomon_name(sensor):
    """Name of the series of a Solomon sensor with metric_type and metric_name in tank monitoring data: the tank
    Solomon sensor puts '-' for '/', '.', '_' in the type and for '/', '.' in the name, convert_name adds custom:."""
    kind, name = re.sub('[/._]', '-', str(sensor['metric_type'])), re.sub('[/.]', '-', str(sensor['metric_name']))
    return 'custom:{}_{}'.format(kind, name)[:SOLOMON_NAME_LEN]


def solomon_problem(sensors, metrics=()):
    """(status, reason) of a Solomon source decided by its panel, None when every sensor is one series under its own
    name and every metric is a sensor. The tank Solomon collector keeps one point per series name and second, so
    several series of a sensor collapse into one, and which of them gets into a point is random."""
    if not sensors:
        return 'unsupported', 'the Solomon panel has no sensors'
    for sensor in sensors:
        query = sensor.get('query') if isinstance(sensor, dict) else None
        if not isinstance(query, str):
            return 'unsupported', 'a Solomon sensor is a selector, not a query with metric_type and metric_name'
        if not (sensor.get('metric_type') and sensor.get('metric_name')):
            return 'unsupported', 'Solomon query {} has no explicit metric_type and metric_name'.format(query)
        if not single_series(query):
            reason = 'Solomon query {} does not aggregate all series into one (series_sum(...) and the like)'
            return 'unsupported', reason.format(query)
    names = sorted({solomon_name(s) for s in sensors})
    for name in metrics:
        if name[:SOLOMON_NAME_LEN] not in names:
            reason = 'metric {} is not a series of the panel: its sensors give {}'.format(name, ', '.join(names))
            return 'error', reason
    return None


def solomon_sensor(sensors, name):
    """The sensor of a panel that gives the series of a section metric, None without one."""
    named = (s for s in sensors if isinstance(s, dict) and s.get('metric_type') and s.get('metric_name'))
    return next((s for s in named if solomon_name(s) == name[:SOLOMON_NAME_LEN]), None)


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _gap(ts, start, edge):
    """Why points at ts (ascending, from start on) do not cover [start, edge), None when they do: a gap over two
    median steps between points, from start to the first point or from the last point to edge. Only the part of a
    gap before edge counts: points are late there."""
    if len(ts) < 2:
        return 'one point'
    step = float(np.median(np.diff(ts)))
    bounds = [start] + ts + [edge]
    widest = max(min(b, edge) - min(a, edge) for a, b in zip(bounds, bounds[1:]))
    if widest > 2 * step:
        return 'a gap of {:g} s, over two median steps of {:g} s'.format(widest, step)
    return None


def _metric_windows(series, windows):
    ts = [t for t, _ in series]
    out = []
    for w in windows:
        values = [v for _, v in series[bisect.bisect_left(ts, w.start) : bisect.bisect_left(ts, w.end)]]
        out.append(
            {
                'window': w.id,
                'points': len(values),
                'mean': sum(values) / len(values) if values else None,
                'min': min(values, default=None),
                'max': max(values, default=None),
            }
        )
    return out


def _evaluate(spec, rows, windows, start, end, tolerance):
    rows = {ts: row for ts, row in rows.items() if start <= ts < end}
    edge = end - tolerance
    if not rows:
        reason = 'no points in the test window'
        if spec['kind'] in SOLOMON_KINDS:
            reason += ' (a token Solomon rejects looks the same, the tank log has the answer)'
        return {'status': 'empty', 'reason': reason, 'points': 0, 'metrics': []}
    if not spec['metrics']:
        gap = _gap(sorted(rows), start, edge)
        return {'status': 'partial' if gap else 'ok', 'reason': gap, 'points': len(rows), 'metrics': []}
    metrics, problems, seen = [], [], set()
    for m in spec['metrics']:
        name = data_name(spec['kind'], m['name'])
        series = sorted((ts, row[name]) for ts, row in rows.items() if _number(row.get(name)))
        seen.update(ts for ts, _ in series)
        gap = _gap([ts for ts, _ in series], start, edge) if series else 'not received'
        if gap:
            problems.append('metric {}: {}'.format(m['name'], gap))
        metrics.append({'name': m['name'], 'unit': m['unit'], 'windows': _metric_windows(series, windows)})
    if not seen:
        return {'status': 'empty', 'reason': '; '.join(problems), 'points': 0, 'metrics': []}
    reason = '; '.join(problems) or None
    return {'status': 'partial' if problems else 'ok', 'reason': reason, 'points': len(seen), 'metrics': metrics}


def monitoring(specs, points, windows, start, end, tolerance):
    """Sources of the section with statuses and metric values by windows.

    specs: sources of the section; status and reason set when the config decides them. points: {chunk key: {ts:
    {data metric name: value}}} as delivered, chunks of one ts glued. Points before S and from E on are dropped. A
    source whose (chunk key, metric) pairs intersect another's is an error: its points cannot be told apart."""
    reads = [(s['host'], {data_name(s['kind'], m['name']) for m in s['metrics']}) for s in specs]
    sources = []
    for spec, (host, names) in zip(specs, reads):
        out = {k: spec[k] for k in ('id', 'kind', 'entity', 'host', 'required')}
        clash = [
            other['id']
            for other, (h, n) in zip(specs, reads)
            if other is not spec and h == host and (not names or not n or names & n)
        ]
        if clash:
            reason = 'ambiguous: source {} reads the same metrics of {}'.format(', '.join(clash), host)
            out.update(status='error', reason=reason)
        elif spec.get('status'):
            out.update(status=spec['status'], reason=spec['reason'])
        else:
            out.update(_evaluate(spec, points.get(host) or {}, windows, start, end, tolerance))
        sources.append(out)
    return sources


def cpu_series(points, start, edge):
    """target.cpu.series of the usage points [(ts, cores)] of the test window [start, E), ascending; edge is
    E - tolerance. A negative usage is no CPU (a counter reset), it is a gap. ts are cut to integer seconds, the later
    point of one second wins. ok needs neighbours exactly a step apart, the first point at most two steps after start
    as for a monitoring source (the real Solomon runs start a whole step after it), and the last at most a step before
    edge. Points missing after edge with no point after them are late, not a gap."""
    cores = {int(ts): value for ts, value in points if value >= 0}
    ts = sorted(cores)
    if len(ts) < 2:
        reason = 'fewer than two points in the test window, the step is unknown'
        return {'status': 'unavailable', 'reason': reason, 'step_s': None, 'points': []}
    steps = [b - a for a, b in zip(ts, ts[1:])]
    step = min(steps)
    gap = max(steps) > step or min(ts[0], edge) - min(start, edge) > 2 * step or edge - ts[-1] > step
    return {
        'status': 'partial' if gap else 'ok',
        'step_s': step,
        'points': [{'ts': t, 'cores': cores[t]} for t in ts],
    }


def target_cpu(conf, sources, windows, per_second, points, tolerance):
    """CPU of the target from its monitoring source; None without one or when the source gave no usage points.
    CPU per request divides by the mean rps of the window seconds up to the last usage point: points come late, and
    the rps of the seconds they have not reached yet would lower it on a rising load. The series of the usage points
    is there only with the series option of the section."""
    if not conf:
        return None
    source = next((s for s in sources if s['id'] == conf['source_id'] and s['entity'] == 'target'), None)
    if source is None or source['status'] not in ('ok', 'partial'):
        return None
    metrics = {m['name']: m['windows'] for m in source['metrics']}
    usage = metrics.get(conf['usage_metric'])
    if not usage or not any(e['points'] for e in usage):
        return None
    throttled = {e['window']: e['mean'] for e in metrics.get(conf.get('throttled_metric')) or []}
    name = data_name(source['kind'], conf['usage_metric'])
    test = next(w for w in windows if w['kind'] == 'test')
    start, end = test['start_ts'], test['end_ts']
    used = sorted(
        (ts, row[name]) for ts, row in points[source['host']].items() if start <= ts < end and _number(row.get(name))
    )
    last = used[-1][0]
    rps = {}
    for w in windows:
        span = [s['rps'] for s in per_second if w['start_ts'] <= s['ts'] < min(w['end_ts'], math.floor(last) + 1)]
        rps[w['id']] = sum(span) / len(span) if span else None
    out = {
        'source_id': source['id'],
        'limit_cores': conf.get('limit_cores'),
        'windows': [
            {
                'window': e['window'],
                'usage_cores_mean': e['mean'],
                'usage_cores_max': e['max'],
                'throttled_cores_mean': throttled.get(e['window']),
                'cpu_ms_per_req': (
                    None if e['mean'] is None or not rps[e['window']] else e['mean'] * 1000 / rps[e['window']]
                ),
            }
            for e in usage
        ],
    }
    if conf.get('series'):
        out['series'] = cpu_series(used, start, end - tolerance)
    return out


# Generator CPU


def _read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return None


def _pairs(path):
    return {
        k: int(v)
        for k, v in (line.split() for line in (_read(path) or '').splitlines() if len(line.split()) == 2)
        if v.isdigit()
    }


def _quota(directory):
    """CPU quota set on one cgroup directory in cores (cpu.max of v2, cfs files of v1), None without one."""
    try:
        text = _read(os.path.join(directory, 'cpu.max'))
        if text is not None:
            quota, period = text.split()
            return None if quota == 'max' else int(quota) / int(period)
        quota = int(_read(os.path.join(directory, 'cpu.cfs_quota_us')) or 0)
        period = int(_read(os.path.join(directory, 'cpu.cfs_period_us')) or 0)
        return quota / period if quota > 0 and period > 0 else None
    except ValueError:
        return None


# source, directory of the usage counter, directory of the throttling counters (where the binding quota is set),
# the lowest quota from the own cgroup up to the mount root in cores or None
Cgroup = namedtuple('Cgroup', 'source usage throttling limit')


def find_cgroup(root, proc_cgroup, pid):
    """(Cgroup, None) of the process pid listed in proc_cgroup (/proc/self/cgroup), or (None, why not). Its
    directory is <mount>/<path of proc_cgroup>; without one the mount shows the own cgroup at its root (a cgroup
    namespace or a bind mount). A directory that does not list pid in cgroup.procs is not the own one: a host mount
    there would pass the CPU of the host for the CPU of the generator."""
    paths = {}
    for line in (_read(proc_cgroup) or '').splitlines():
        parts = line.split(':', 2)
        if len(parts) == 3:
            for controller in parts[1].split(','):
                paths[controller] = parts[2]
    if '' in paths and os.path.exists(os.path.join(root, 'cgroup.controllers')):
        source, usage_mount, usage_path, cpu_mount, cpu_path = 'cgroup_v2', root, paths[''], root, paths['']
    elif 'cpuacct' in paths and 'cpu' in paths:
        source = 'cgroup_v1'
        usage_mount, usage_path = os.path.join(root, 'cpuacct'), paths['cpuacct']
        cpu_mount, cpu_path = os.path.join(root, 'cpu'), paths['cpu']
    else:
        return None, 'no cpu controller in {}'.format(proc_cgroup)

    def own(mount, path):
        directory = os.path.normpath(os.path.join(mount, path.lstrip('/')))
        return directory if os.path.isdir(directory) else os.path.normpath(mount)

    usage, directory = own(usage_mount, usage_path), own(cpu_mount, cpu_path)
    if str(pid) not in (_read(os.path.join(usage, 'cgroup.procs')) or '').split():
        return None, '{} does not list the tank process: not its cgroup'.format(usage)
    limit, throttling = None, directory
    while True:
        quota = _quota(directory)
        if quota is not None and (limit is None or quota < limit):
            limit, throttling = quota, directory
        if directory == os.path.normpath(cpu_mount):
            break
        directory = os.path.dirname(directory)
    return Cgroup(source, usage, throttling, limit), None


def cgroup_cpu(cgroup):
    """Cumulative (usage_s, throttled_s, periods, throttled_periods) of a Cgroup, None without the usage counter;
    a throttling counter the cgroup does not have is None. CPU of an interval is a difference of two."""
    usage_stat = _pairs(os.path.join(cgroup.usage, 'cpu.stat'))
    stat = _pairs(os.path.join(cgroup.throttling, 'cpu.stat'))
    if cgroup.source == 'cgroup_v2':
        usage = usage_stat['usage_usec'] / 1e6 if 'usage_usec' in usage_stat else None
        throttled = stat['throttled_usec'] / 1e6 if 'throttled_usec' in stat else None
    else:
        try:
            usage = int(_read(os.path.join(cgroup.usage, 'cpuacct.usage'))) / 1e9
        except (TypeError, ValueError):
            usage = None
        throttled = stat['throttled_time'] / 1e9 if 'throttled_time' in stat else None
    if usage is None:
        return None
    return usage, throttled, stat.get('nr_periods'), stat.get('nr_throttled')


def _known(snapshots, *indexes):
    return bool(snapshots) and all(s[i] is not None for s in snapshots for i in indexes)


def generator_cpu(source, snapshots, capacity, windows):
    """CPU of the tank container by windows from snapshots [(s, usage_s, throttled_s, periods, throttled_periods)]
    of its cumulative counters, ascending by a monotonic clock in epoch seconds: an interval between two snapshots
    adds to a window in proportion to their overlap. util_pct is relative to capacity, the quota or the cores
    without one. Throttling the cgroup does not count is null."""
    if source == 'unavailable':
        return {'source': source, 'windows': []}
    has_throttled, has_periods = _known(snapshots, 2), _known(snapshots, 3, 4)
    intervals = [
        (a[0], b[0]) + tuple((y or 0) - (x or 0) for x, y in zip(a[1:], b[1:]))
        for a, b in zip(snapshots, snapshots[1:])
        if b[0] > a[0]
    ]
    ends = [i[1] for i in intervals]
    out = []
    for w in windows:
        covered = usage = throttled = periods = slowed = 0
        peak = None
        for t0, t1, du, dt, dp, dslowed in intervals[bisect.bisect_right(ends, w.start) :]:
            if t0 >= w.end:
                break
            overlap = min(t1, w.end) - max(t0, w.start)
            share = overlap / (t1 - t0)
            covered += overlap
            usage += share * du
            throttled += share * dt
            periods += share * dp
            slowed += share * dslowed
            peak = max(du / (t1 - t0), peak or 0)
        mean = usage / covered if covered else None
        out.append(
            {
                'window': w.id,
                'usage_cores_mean': mean,
                'usage_cores_max': peak,
                'util_pct_mean': None if mean is None else mean * 100 / capacity,
                'util_pct_max': None if peak is None else peak * 100 / capacity,
                'throttled_periods_pct': slowed * 100 / periods if periods and has_periods else None,
                'throttled_s': throttled if covered and has_throttled else None,
                'throttled_cores_mean': throttled / covered if covered and has_throttled else None,
            }
        )
    return {'source': source, 'windows': out}


def _ratio_peak(num, den, length):
    """Highest sum(num) / sum(den) in percent over length items in a row (all of them when fewer); None when den
    never sums above zero."""
    n = min(length, len(den))
    if not n:
        return None
    sums = [np.concatenate([[0.0], np.cumsum(np.asarray(v, dtype=float))]) for v in (num, den)]
    top, bottom = (s[n:] - s[:-n] for s in sums)
    ok = bottom > 0
    return float((top[ok] / bottom[ok]).max() * 100) if ok.any() else None


def _held_peak(values, length):
    """Highest value held for length known items in a row (all of them when fewer); None items are skipped."""
    values = [v for v in values if v is not None]
    n = min(length, len(values))
    if not n:
        return None
    return int(np.lib.stride_tricks.sliding_window_view(np.array(values), n).min(axis=1).max())


def _rate_peak(snapshots, num, den, length):
    """Highest growth of counter num per growth of den (0 is the clock) over length seconds of snapshots in a row
    (all of them when they span less); None when den does not grow."""
    if len(snapshots) < 2 or not _known(snapshots, num, den):
        return None
    times = [s[0] for s in snapshots]
    length = min(length, times[-1] - times[0])
    best = None
    for a in snapshots:
        j = bisect.bisect_left(times, a[0] + length - 1e-6)
        if j == len(snapshots):
            break
        b = snapshots[j]
        if b[den] > a[den]:
            best = max(best or 0, (b[num] - a[num]) / (b[den] - a[den]))
    return best


def saturation(thresholds, snapshots, capacity, windows, per_second, pools):
    """Signals of the generator being the bottleneck that crossed their thresholds in the test and steady windows.
    A value is the highest over sustain_s seconds in a row of the window (all of it when shorter): a second-long
    burst does not count, and the end of a ramp is not averaged away. The instances threshold is the sum of the
    startup instances of the pools; seconds without instances are skipped. PLAN_NOT_MET is mostly the share of
    discarded shots, but it also catches seconds without data: a generator that stalled discards nothing."""
    length = thresholds['sustain_s']
    seconds = {s['ts']: s for s in per_second}
    limits = [pool.profile['instances'] for pool in pools]
    limit = None if None in limits else sum(limits)
    signals, judged = [], False
    for w in windows:
        if w['kind'] not in ('test', 'steady'):
            continue
        span = [seconds[ts] for ts in range(w['start_ts'], w['end_ts'])]
        responses = [s['rps'] for s in span]
        discarded = [s['net_codes'].get(DISCARDED_CODE, 0) for s in span]
        planned = [s['planned_rps'] for s in span]
        cpu = [s for s in snapshots if w['start_ts'] <= s[0] <= w['end_ts']]
        util = _rate_peak(cpu, 1, 0, length)
        throttled = _rate_peak(cpu, 4, 3, length)
        for code, value, unit, threshold in (
            ('CPU_UTIL_HIGH', None if util is None else util * 100 / capacity, 'pct', thresholds['cpu_util_pct']),
            (
                'CPU_THROTTLED',
                None if throttled is None else throttled * 100,
                'pct',
                thresholds['cpu_throttled_periods_pct'],
            ),
            (
                'DISCARDED_SHOTS',
                _ratio_peak(discarded, [r + d for r, d in zip(responses, discarded)], length),
                'pct',
                thresholds['discarded_shots_pct'],
            ),
            (
                'PLAN_NOT_MET',
                None if None in planned else _ratio_peak([p - r for p, r in zip(planned, responses)], planned, length),
                'pct',
                thresholds['plan_deficit_pct'],
            ),
            (
                'INSTANCES_EXHAUSTED',
                _held_peak([s['instances'] for s in span], length) if limit else None,
                'count',
                limit,
            ),
        ):
            if value is None:
                continue
            judged = True
            if value >= threshold:
                signals.append({'code': code, 'window': w['id'], 'value': value, 'unit': unit, 'threshold': threshold})
    return {'status': 'saturated' if signals else 'not_saturated' if judged else 'unknown', 'signals': signals}


def completeness(sources):
    blocking = [s['id'] for s in sources if s['required'] and s['status'] in ('empty', 'error', 'unsupported')]
    if blocking:
        return {'status': 'INCOMPLETE', 'blocking': True, 'blocking_sources': blocking}
    status = 'PARTIAL' if any(s['status'] not in ('ok', 'not_requested') for s in sources) else 'COMPLETE'
    return {'status': status, 'blocking': False, 'blocking_sources': []}


def generator_dc(dc, dc_env, environ):
    """The section dc, then the first set variable of dc_env up to the first dot (dc-a.<domain> gives dc-a)."""
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
