"""Report schemas against fixtures: every file in fixtures/<kind>/valid passes,
every mutation listed in fixtures/<kind>/invalid.json fails.

contrib jsonschema is 3.2.0 and knows draft-07 at most, so the schemas are written in
the subset where draft 2020-12 and draft-07 agree; test_schema_keywords keeps them there.
The Go test in load/projects/ai_analysis/report runs the same fixtures through a real
2020-12 validator.
"""

import hashlib
import json
import math
import os
import re
from fractions import Fraction

import pytest

# The GitHub mirror does not install jsonschema for the tank tests.
jsonschema = pytest.importorskip('jsonschema')

ROOT = 'load/projects/yandex-tank/yandextank/plugins/MachineReport'
SCHEMAS = {
    'machine_report': 'machine_report.v1.schema.json',
    'hist': 'hist.v1.schema.json',
}

# Keywords with the same meaning in draft-07 and 2020-12. Anything else
# (prefixItems, unevaluatedProperties, dependentRequired, ...) would be silently
# ignored by the validator here.
KEYWORDS = {
    '$schema', '$defs', '$ref', '$comment', 'title', 'description', 'format',
    'type', 'enum', 'const', 'required', 'properties', 'patternProperties',
    'additionalProperties', 'propertyNames', 'items', 'contains', 'minItems', 'maxItems',
    'uniqueItems', 'pattern', 'minLength', 'maxLength', 'minimum', 'maximum',
    'exclusiveMinimum', 'exclusiveMaximum', 'allOf', 'anyOf', 'oneOf', 'not', 'if', 'then', 'else',
}  # fmt: skip
# date-time is asserted without optional packages: 3.2.0 checks it only when an RFC 3339 library is installed.
FORMATS = jsonschema.FormatChecker(())
RFC3339 = re.compile(r'^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$')


@FORMATS.checks('date-time')
def is_date_time(value):
    return not isinstance(value, str) or RFC3339.match(value) is not None


SUBSCHEMA_MAPS = ('properties', 'patternProperties', '$defs')
SUBSCHEMAS = ('items', 'additionalProperties', 'propertyNames', 'contains', 'not', 'if', 'then', 'else')
SUBSCHEMA_LISTS = ('allOf', 'anyOf', 'oneOf')


def source(*parts):
    # Same fallback as yandextank.common.util.get_test_path: the directory is also synced to GitHub.
    try:
        import yatest.common

        root = yatest.common.source_path(ROOT)
    except ImportError:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, *parts)


def load(path):
    with open(path) as f:
        return json.load(f)


def validator(kind):
    schema = load(source('schema', SCHEMAS[kind]))
    jsonschema.Draft7Validator.check_schema(schema)
    return jsonschema.Draft7Validator(schema, format_checker=FORMATS)


def errors(v, kind, doc):
    """Schema errors plus what JSON Schema cannot say (report.Validate checks the same)."""
    found = ['{}: {}'.format(list(e.absolute_path), e.message) for e in v.iter_errors(doc)]
    if kind == 'hist' and not found:
        upper, counts = doc['upper_us'], doc['counts']
        if len(upper) != len(counts):
            found.append('upper_us and counts differ in length')
        if any(b <= a for a, b in zip(upper, upper[1:])):
            found.append('upper_us is not strictly ascending')
    if kind == 'machine_report' and not found:
        found += report_errors(doc)
    return found


QUANTILE_KEY = re.compile(r'^p(100|[1-9][0-9]?(\.[0-9]{1,3})?)$')


def latency_errors(where, agg):
    """Nearest rank of $defs/latencyMs: a quantile is null exactly when k = ceil(p * responses / 100) is in overflow.
    Integers are read by value (240.0 is 240), as JSON Schema and report.Validate do; the rank is exact."""
    responses, latency = int(agg['responses']), agg['latency_ms']
    if (latency is None) != (responses == 0):
        return ['{}: latency_ms must be null exactly when responses is 0'.format(where)]
    found = []
    for key, value in (latency or {}).items():
        if not QUANTILE_KEY.match(key):
            found.append('{}: quantile key {} is not p1..p99.999 or p100'.format(where, key))
            continue
        k = math.ceil(Fraction(key[1:]) * responses / 100)
        if (value is None) != (k > responses - int(agg['latency_overflow'])):
            found.append('{}: {} is {} with rank {} of {}'.format(where, key, value, k, responses))
    return found


def sent_errors(where, sent, net_codes):
    """responses of a window and rps of a second are sum(net_codes) - net_codes['777']: discarded shots are unsent."""
    total = sum(int(n) for code, n in net_codes.items() if code != '777')
    return [] if total == int(sent) else ['{}: {} sent, but net codes without 777 sum to {}'.format(where, sent, total)]


def report_errors(doc):
    """Unique window ids and phases, a window per started phase, id number equal to phase_index, pool of a phase
    naming a pool, every window within the test window and at least a second long, quantile ranks, responses and
    rps equal to net codes without 777, per_second covering the test window second by second, CPU and monitoring
    for the test and steady windows, load_profile hash."""
    found = []
    ids = [w['id'] for w in doc['windows']]
    if len(set(ids)) != len(ids):
        found.append('window ids repeat')
    phases = {int(p['index']): p for p in doc['phases']}
    if len(phases) != len(doc['phases']):
        found.append('phase indexes repeat')
    pools = len(doc['provenance']['load_profile']['pools'])
    for index, p in phases.items():
        if 'pool' in p and int(p['pool']) >= pools:
            found.append('phase {} names no pool of load_profile'.format(index))
    test = next(w for w in doc['windows'] if w['kind'] == 'test')
    start, end = int(test['start_ts']), int(test['end_ts'])
    for index, p in phases.items():
        if test['start_ts'] + p['start_offset_s'] < test['end_ts'] and 'phase-{}'.format(index) not in ids:
            found.append('phase {} started but has no window'.format(index))
    if [int(s['ts']) for s in doc['load']['per_second']] != list(range(start, end)):
        found.append('per_second does not cover the test window second by second')
    for w in doc['windows']:
        if not start <= int(w['start_ts']) < int(w['end_ts']) <= end:
            found.append('window {} is not within the test window or shorter than a second'.format(w['id']))
        found += latency_errors('window ' + w['id'], w)
        found += sent_errors('window ' + w['id'], w['responses'], w['net_codes'])
        for name, case in w.get('cases', {}).items():
            found += latency_errors('window {} case {}'.format(w['id'], name), case)
        if w['kind'] == 'test':
            continue
        if w['id'] != '{}-{}'.format(w['kind'], int(w['phase_index'])):
            found.append('window {} has phase_index {}'.format(w['id'], w['phase_index']))
        phase = phases.get(int(w['phase_index']))
        if phase is None:
            found.append('window {} names no phase'.format(w['id']))
        elif w['kind'] == 'steady' and phase['kind'] != 'const':
            found.append('window {} is on a {} phase'.format(w['id'], phase['kind']))
    for second in doc['load']['per_second']:
        found += sent_errors('second {}'.format(second['ts']), second['rps'], second['net_codes'])
    derivable = [w['id'] for w in doc['windows'] if w['kind'] in ('test', 'steady')]
    covered = {}
    if doc['generator']['cpu']['source'] != 'unavailable':
        covered['generator.cpu'] = doc['generator']['cpu']['windows']
    if doc['target']['cpu'] is not None:
        covered['target.cpu'] = doc['target']['cpu']['windows']
    for s in doc['monitoring']['sources']:
        if s['status'] in ('ok', 'partial'):
            for m in s.get('metrics', []):
                covered['monitoring {}/{}'.format(s['id'], m['name'])] = m['windows']
    for where, entries in covered.items():
        missing = set(derivable) - {e['window'] for e in entries}
        if missing:
            found.append('{} has no entry for {}'.format(where, sorted(missing)))
    profile = json.dumps(doc['provenance']['load_profile'], sort_keys=True, separators=(',', ':'))
    if hashlib.sha256(profile.encode()).hexdigest() != doc['provenance']['load_profile_sha256']:
        found.append('load_profile_sha256 is not the sha256 of the canonical load_profile')
    return found


def mutate(doc, case):
    """Applies one invalid.json case: sets value at the JSON pointer, or removes the key when there is no value."""
    *parents, last = case['path'].split('/')[1:]
    node = doc
    for key in parents:
        node = node[int(key)] if isinstance(node, list) else node[key]
    if isinstance(node, list):
        last = int(last)
    if 'value' in case:
        node[last] = case['value']
    else:
        del node[last]  # KeyError on a mistyped path: the case must not pass by accident


def walk(node, where):
    unknown = set(node) - KEYWORDS
    assert not unknown, (where, sorted(unknown))
    if '$ref' in node:
        # draft-07 ignores everything next to $ref
        assert set(node) <= {'$ref', 'description'}, where
    for key in SUBSCHEMA_MAPS:
        for name, sub in node.get(key, {}).items():
            walk(sub, '{}/{}/{}'.format(where, key, name))
    for key in SUBSCHEMAS:
        if isinstance(node.get(key), dict):
            walk(node[key], '{}/{}'.format(where, key))
    for key in SUBSCHEMA_LISTS:
        for i, sub in enumerate(node.get(key, [])):
            walk(sub, '{}/{}/{}'.format(where, key, i))


@pytest.mark.parametrize('kind', sorted(SCHEMAS))
def test_schema_keywords(kind):
    walk(load(source('schema', SCHEMAS[kind])), kind)


@pytest.mark.parametrize('kind', sorted(SCHEMAS))
def test_valid_fixtures_pass(kind):
    v = validator(kind)
    names = sorted(os.listdir(source('tests', 'fixtures', kind, 'valid')))
    assert names
    for name in names:
        doc = load(source('tests', 'fixtures', kind, 'valid', name))
        assert not errors(v, kind, doc), name


@pytest.mark.parametrize('kind', sorted(SCHEMAS))
def test_invalid_mutations_fail(kind):
    v = validator(kind)
    cases = load(source('tests', 'fixtures', kind, 'invalid.json'))
    assert cases
    for case in cases:
        doc = load(source('tests', 'fixtures', kind, 'valid', case['base']))
        mutate(doc, case)
        assert errors(v, kind, doc), case['name']


def test_integers_by_value():
    """240.0 is an integer for JSON Schema; report_errors reads it by value, as report.Validate does."""

    def respell(node):
        if isinstance(node, dict):
            return {k: respell(v) for k, v in node.items()}
        if isinstance(node, list):
            return [respell(v) for v in node]
        return float(node) if type(node) is int else node

    doc = load(source('tests', 'fixtures', 'machine_report', 'valid', 'ok.json'))
    for key in ('phases', 'windows', 'load'):
        doc[key] = respell(doc[key])
    assert not errors(validator('machine_report'), 'machine_report', doc)
