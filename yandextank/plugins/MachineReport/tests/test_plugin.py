"""The MachineReport plugin in the tank lifecycle: files it writes, what it never breaks, and that it stays inert
without its section."""

import functools
import gzip
import json
import logging
import os
import threading
import types

import pytest
import yaml

from load.contrib.netort.resource import make_resource_manager, manager
from yandextank.common.interfaces import DummyCollector
from yandextank.plugins.MachineReport import plugin as machine_report
from yandextank.plugins.MachineReport import report
from yandextank.stepper.main import StepperWrapper
from yandextank.validator.validator import TankConfig, ValidationError, load_core_base_cfg, load_plugin_schema

from test_report import (
    CGROUP_V2,
    PID,
    T,
    aggregate,
    cgroup,
    const,
    once,
    pandora_pool,
    phout,
    stepper_wrapper,
    stpd,
    tank_cgroup,
    tank_stepper,
)
from test_schema import errors, load, source, validator

VERSION_STUB = '#!/bin/sh\necho "Pandora core/0.8.3" >&2\n'


class Job(object):
    def __init__(self, generator):
        self.generator_plugin = generator
        self.listeners = []

    def subscribe_plugin(self, plugin):
        self.listeners.append(plugin)


class Config(object):
    def __init__(self, validated):
        self.validated = validated

    def get_option(self, section, option, default=None):
        return self.validated.get(section, {}).get(option, default)


class Core(object):
    def __init__(self, directory, generator, config=None, plugins=None):
        self.artifacts_dir = str(directory)
        self.job = Job(generator)
        self.interrupted = threading.Event()
        self.resource_manager = None
        self.test_id = '2026-09-30_12-00-00.000000'
        self.config = Config(config or {'core': {'aggregator_max_wait': 31}})
        self.plugins = plugins or {}

    def get_option(self, section, option, default=None):
        return self.config.get_option(section, option, default)


@pytest.fixture(autouse=True)
def no_host_cgroup(tmp_path, monkeypatch):
    """Tests do not read the cgroup of the machine they run on."""
    monkeypatch.setattr(machine_report, 'CGROUP_ROOT', str(tmp_path / 'no-cgroup'))
    monkeypatch.setattr(machine_report, 'PROC_CGROUP', str(tmp_path / 'no-proc-cgroup'))


def own_cgroup(tmp_path, monkeypatch, files):
    root, proc = tank_cgroup(tmp_path, files)
    monkeypatch.setattr(machine_report, 'CGROUP_ROOT', root)
    monkeypatch.setattr(machine_report, 'PROC_CGROUP', proc)
    return root


def stub(tmp_path, text=VERSION_STUB, name='pandora'):
    path = tmp_path / name
    path.write_text(text)
    path.chmod(0o755)
    return str(path)


def generator(tmp_path, schedules=([const(10, '10s')],), section='pandora'):
    return types.SimpleNamespace(
        SECTION=section,
        config_contents={'pools': [pandora_pool(rps) for rps in schedules]},
        pandora_cmd=stub(tmp_path),
    )


def make(tmp_path, section=None, **kwargs):
    artifacts = tmp_path / 'artifacts'
    artifacts.mkdir()
    core = Core(artifacts, kwargs.pop('gen', None) or generator(tmp_path), **kwargs)
    return machine_report.Plugin(core, dict(section or {}), 'machine_report'), core


def shoot(plugin, seconds=5):
    rows = [(T + s + 0.1 * i, 'a', 1000 + 100 * i, 0, 200) for s in range(seconds) for i in range(10)]
    for data in aggregate([[phout(rows)]]):
        plugin.on_aggregated_data(data, {'ts': data['ts'], 'metrics': {'instances': 3, 'reqps': 10}})


def files(core):
    return sorted(os.listdir(core.artifacts_dir))


def published(core):
    with open(os.path.join(core.artifacts_dir, report.REPORT_FILE)) as f:
        doc = json.load(f)
    hist_path = os.path.join(core.artifacts_dir, report.HIST_FILE)
    with gzip.open(hist_path, 'rt') as f:
        lines = [json.loads(li) for li in f]
    assert not errors(validator('machine_report'), 'machine_report', doc)
    v = validator('hist')
    for li in lines:
        assert not errors(v, 'hist', li)
    histograms = doc['artifacts']['histograms']
    assert histograms['sha256'] == report.file_sha256(hist_path)
    assert histograms['bytes'] == os.path.getsize(hist_path)
    assert histograms['lines'] == len(lines)
    return doc


def test_lifecycle(tmp_path, monkeypatch):
    own_cgroup(tmp_path, monkeypatch, {'cgroup.controllers': '', 'cgroup.procs': str(PID), 'cpu.max': '200000 100000'})
    plugin, core = make(tmp_path)
    plugin.configure()
    assert core.job.listeners == [plugin]
    plugin.prepare_test()
    assert plugin._pools and plugin._gun_version == '0.8.3'  # read before the shooting
    plugin.start_test()
    shoot(plugin)
    assert plugin.post_process(0) == 0
    assert files(core) == [report.HIST_FILE, report.REPORT_FILE]
    doc = published(core)
    assert doc['statuses']['shooting'] == {'status': 'DONE', 'retcode': 0, 'autostop_criterion': None}
    assert doc['statuses']['completeness'] == {'status': 'COMPLETE', 'blocking': False, 'blocking_sources': []}
    assert doc['load']['gun'] == {'type': 'pandora', 'version': '0.8.3', 'grpc_status': 'not_applicable'}
    assert doc['generator']['cpu_limit_cores'] == 2.0
    assert doc['provenance']['tank_job_id'] == core.test_id
    assert doc['provenance']['test_id'] is None
    assert doc['target']['address'] == 'target:80'
    assert doc['perforator'] == {'status': 'not_requested'}
    assert doc['generator']['dc'] is None  # dc_env is empty by default
    assert [s['instances'] for s in doc['load']['per_second']] == [3] * 5
    # repeated post_process changes nothing
    mtime = os.stat(os.path.join(core.artifacts_dir, report.REPORT_FILE)).st_mtime_ns
    assert plugin.post_process(0) == 0
    assert os.stat(os.path.join(core.artifacts_dir, report.REPORT_FILE)).st_mtime_ns == mtime


def test_section_values(tmp_path, monkeypatch):
    monkeypatch.setenv('NODE_CLUSTER', 'dc-b.cluster.example')
    monkeypatch.delenv('NODE_DC', raising=False)
    section = {
        'generator': {'dc_env': ['NODE_DC', 'NODE_CLUSTER']},
        'monitoring': [
            {'kind': 'telegraf', 'host': 'target-1', 'required': True},
            {'id': 'cpu', 'kind': 'solomon', 'host': 'target_cpu', 'entity': 'target'},
        ],
        'target': {'address': 'svc:443', 'hosts': [{'host': 'pod-1', 'dc': 'dc-a', 'cpu_model': 'EPYC'}]},
        'perforator': {
            'microscope_id': 'm-1',
            'selector': '{service="svc"}',
            'process_comm': 'svc',
            'microscope_window': {'start_ts': T - 60, 'end_ts': T + 600},
        },
    }
    config = {
        'core': {'aggregator_max_wait': 31},
        'metaconf': {'firestarter': {'labels': {'series': 's-1', 'run': 'r-1'}, 'dc': 'dc-a'}},
    }
    plugin, core = make(tmp_path, section, config=config)
    plugin.configure()
    plugin.start_test()
    shoot(plugin)
    plugin.post_process(0)
    doc = published(core)
    # telegraf gave no points; there is no Solomon plugin with the panel in the config
    assert [(s['id'], s['status'], s['required']) for s in doc['monitoring']['sources']] == [
        ('telegraf:target-1', 'empty', True),
        ('cpu', 'not_requested', False),
    ]
    assert doc['statuses']['completeness'] == {
        'status': 'INCOMPLETE',
        'blocking': True,
        'blocking_sources': ['telegraf:target-1'],
    }
    assert doc['target'] == {
        'address': 'svc:443',
        'hosts': [{'host': 'pod-1', 'dc': 'dc-a', 'cpu_model': 'EPYC', 'cpu_model_source': 'config'}],
        'cpu': None,
    }
    assert doc['perforator']['status'] == 'pending'
    assert doc['provenance']['labels'] == {'series': 's-1', 'run': 'r-1'}
    assert doc['provenance']['series'] == 's-1'
    assert doc['generator']['dc'] == 'dc-b'


def test_stopped_and_autostopped(tmp_path):
    for sub in ('stop', 'autostop'):
        (tmp_path / sub).mkdir()
    plugin, core = make(tmp_path / 'stop')
    core.interrupted.set()
    plugin.configure()
    plugin.start_test()
    shoot(plugin)
    assert plugin.post_process(1) == 1
    assert published(core)['statuses']['shooting']['status'] == 'STOPPED'

    cause = object()
    autostop = types.SimpleNamespace(
        SECTION='autostop',
        cause_criterion=cause,
        _criterions={'limit(10m)': object(), 'quantile(99,100ms,5s)': cause},
        get_option=lambda name: ['limit(10m)', 'quantile(99,100ms,5s)'],
    )
    plugin, core = make(tmp_path / 'autostop', plugins={'plugin_autostop': autostop})
    plugin.configure()
    plugin.start_test()
    shoot(plugin)
    assert plugin.post_process(28) == 28
    doc = published(core)
    assert doc['statuses']['shooting'] == {
        'status': 'AUTOSTOPPED',
        'retcode': 28,
        'autostop_criterion': 'quantile(99,100ms,5s)',
    }
    assert doc['load']['autostop_criteria'] == ['limit(10m)', 'quantile(99,100ms,5s)']


def fail(*args, **kwargs):
    raise OSError('injected')


def fail_second_call(real):
    calls = []

    def replace(*args):
        calls.append(args)
        if len(calls) == 2:
            raise OSError('injected')
        return real(*args)

    return replace


@pytest.mark.parametrize(
    'stage',
    ['summarize', 'hist_write', 'build', 'config_hash', 'replace_hist', 'write_report', 'no_seconds', 'lost_code'],
)
def test_no_files_and_same_retcode_on_errors(tmp_path, monkeypatch, stage):
    plugin, core = make(tmp_path)
    if stage == 'summarize':
        monkeypatch.setattr(report, 'summarize_second', fail)
    elif stage == 'hist_write':
        monkeypatch.setattr(report.HistWriter, 'write', fail)
    elif stage == 'build':
        monkeypatch.setattr(report, 'build', fail)
    elif stage == 'config_hash':
        monkeypatch.setattr(report, 'config_sha256', fail)
    elif stage == 'replace_hist':
        monkeypatch.setattr(machine_report.os, 'replace', fail)
    elif stage == 'write_report':
        monkeypatch.setattr(machine_report.os, 'replace', fail_second_call(os.replace))
    plugin.configure()
    plugin.start_test()
    if stage == 'lost_code':
        # 777 outside the discarded tag: the second cannot be attributed, the aggregate is lost
        for data in aggregate([[phout([(T, 'a', 0, 777, 0)])]]):
            plugin.on_aggregated_data(data, None)
    if stage != 'no_seconds':
        shoot(plugin)
    assert plugin.post_process(3) == 3
    assert files(core) == []


def test_post_process_without_start(tmp_path, caplog):
    plugin, core = make(tmp_path)
    plugin.configure()
    shoot(plugin)  # ignored: the plugin has not started
    with caplog.at_level(logging.WARNING):
        assert plugin.post_process(1) == 1
    assert files(core) == []
    assert 'did not start' in caplog.text


@pytest.mark.parametrize('section', ['jmeter', 'other'])
def test_other_generators(tmp_path, section):
    plugin, core = make(tmp_path, gen=generator(tmp_path, section=section))
    plugin.configure()
    plugin.start_test()
    shoot(plugin)
    assert plugin.post_process(0) == 0
    assert files(core) == []


def stable(doc):
    """A report without the fields of the machine and the moment."""
    d = json.loads(json.dumps(doc))
    for key in ('created_at', 'tank_version', 'plugin_version'):
        del d['provenance'][key]
    for key in ('host', 'cpu_model', 'cores'):
        del d['generator'][key]
    for key in ('sha256', 'bytes'):
        del d['artifacts']['histograms'][key]
    return d


def same_as_fixture(doc, name):
    """The report is a valid fixture (the Go report.Validate checks it too) and stays what the plugin writes;
    MACHINE_REPORT_REGEN=<directory> writes it there."""
    path = source('tests', 'fixtures', 'machine_report', 'valid', name)
    if os.environ.get('MACHINE_REPORT_REGEN'):
        with open(os.path.join(os.environ['MACHINE_REPORT_REGEN'], name), 'w') as f:
            json.dump(doc, f, indent=1, ensure_ascii=False)
    assert stable(doc) == stable(load(path))


def stream(schedule, load_type='rps', tank_type='http', ssl=0, address='target', port=80, **options):
    """A phantom stream (the main section or a multi one) after configure: its stepper has run."""
    wrapper = stepper_wrapper(schedule, load_type, **options)
    return types.SimpleNamespace(stepper_wrapper=wrapper, tank_type=tank_type, ssl=ssl, address=address, port=port)


def phantom(*streams):
    return types.SimpleNamespace(SECTION='phantom', phantom=types.SimpleNamespace(streams=list(streams)))


def bfg(schedule, load_type='rps', module=None, **options):
    """A bfg generator after configure; module: the module of its plugin class, bfg2020 is recognized by it."""
    section = dict({'gun_type': 'custom', 'gun_config': {'module_name': 'gun'}}, **options.pop('section', {}))
    plugin = type('Plugin', (types.SimpleNamespace,), {'__module__': module}) if module else types.SimpleNamespace
    return plugin(
        SECTION='bfg',
        stepper_wrapper=stepper_wrapper(schedule, load_type, ammo_type='caseline', **options),
        get_option=lambda name, default=None: section.get(name, default),
    )


def run(plugin):
    plugin.configure()
    plugin.prepare_test()
    plugin.start_test()
    shoot(plugin)
    return plugin.post_process(0)


def test_phantom_multi(tmp_path):
    """The main section and a multi one are two pools in config order; phantom has no version source."""
    gen = phantom(
        stream('line(1,10,2s) const(10,1m)'),
        stream('const(2,1m)', 'instances', tank_type='none', address='other', instances=2),
    )
    plugin, core = make(tmp_path, gen=gen)
    assert run(plugin) == 0
    assert files(core) == [report.HIST_FILE, report.REPORT_FILE]
    doc = published(core)
    assert doc['load']['gun'] == {'type': 'phantom', 'version': None, 'grpc_status': 'not_applicable'}
    assert [
        (p['gun'], p['load_type'], p['transport'], p['target_protocol'])
        for p in doc['provenance']['load_profile']['pools']
    ] == [
        ('phantom', 'rps', 'http1', 'http'),
        ('phantom', 'instances', 'other', 'other'),
    ]
    assert [(p['pool'], p['kind']) for p in doc['phases']] == [(0, 'line'), (0, 'const'), (1, 'const')]
    assert doc['target']['address'] == 'target:80'
    assert {s['planned_rps'] for s in doc['load']['per_second']} == {None}
    same_as_fixture(doc, 'phantom_multi.json')


def test_phantom_multi_shared_pause(tmp_path, caplog):
    """Each stream alone passes, together they are silent for 60 s on their one phout: no report, same retcode."""
    gen = phantom(stream('const(10,60s)'), stream('const(0,120s) const(10,60s)'))
    plugin, core = make(tmp_path, gen=gen)
    with caplog.at_level(logging.WARNING):
        assert run(plugin) == 0
    assert files(core) == []
    assert 'aggregator_max_wait' in caplog.text and 'one aggregator source' in caplog.text


@pytest.mark.parametrize(
    'section, pool',
    [
        ({}, ('other', 'other', 'unknown')),
        (
            {'gun_type': 'http', 'gun_config': {'base_address': 'https://target.example.net'}},
            ('http1_tls', 'http', 'https://target.example.net'),
        ),
        (
            {'gun_type': 'http', 'gun_config': {'base_address': 'http://target.example.net'}, 'address': 'target:80'},
            ('http1', 'http', 'target:80'),
        ),
    ],
)
def test_bfg(tmp_path, section, pool):
    """bfg is one pool; http by the scheme of base_address, any other gun is other. The ammo file is hashed by the
    bytes the stepper readers get."""
    ammo = tmp_path / 'ammo.txt'
    ammo.write_bytes(b'/\n')
    plugin, core = make(tmp_path, gen=bfg('const(10,1m)', uris=[], ammo_file=str(ammo), section=section))
    core.resource_manager = manager
    assert run(plugin) == 0
    doc = published(core)
    [profile] = doc['provenance']['load_profile']['pools']
    assert (profile['transport'], profile['target_protocol'], doc['target']['address']) == pool
    assert (profile['gun'], profile['ammo_type'], doc['load']['gun']['type']) == ('bfg', 'caseline', 'bfg')
    assert profile['ammo_sha256'] == report.file_sha256(str(ammo))


@pytest.mark.parametrize(
    'module, section, instances',
    [
        (None, {}, 4),
        (None, {'worker_type': 'green'}, 4000),
        (None, {'worker_type': 'green', 'green_threads_per_instance': 10}, 40),
        (machine_report.BFG2020_MODULE, {'worker_type': 'green'}, 4),
        (machine_report.BFG2020_MODULE, {'worker_type': 'green', 'green_threads_per_instance': 10}, 4),
    ],
)
def test_bfg_green_worker_instances(tmp_path, module, section, instances):
    """The green worker keeps green_threads_per_instance shots in flight in each of its processes: its instances
    counter grows up to their product, which is the limit the pool shoots with. bfg2020 starts only processes."""
    plugin, core = make(tmp_path, gen=bfg('const(10,1m)', module=module, instances=4, section=section))
    assert run(plugin) == 0
    [profile] = published(core)['provenance']['load_profile']['pools']
    assert profile['instances'] == instances


def test_bfg2020_unprepared_stepper(tmp_path, caplog):
    """A bfg2020 whose stepper has not run by prepare_test: no report and a warning, not a traceback."""
    gen = bfg('const(10,10s)', module=machine_report.BFG2020_MODULE)
    gen.stepper_wrapper = tank_stepper(tmp_path, 'const(10,10s)', stage=0)
    plugin, core = make(tmp_path, gen=gen)
    with caplog.at_level(logging.WARNING):
        assert run(plugin) == 0
    assert files(core) == []
    assert 'MachineReport: no report will be written: the bfg stepper has not run' in caplog.text
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


@pytest.mark.parametrize(
    'options',
    [
        {},
        {'ammofile': 'ammo.txt', 'ammo_type': 'line', 'uris': [], 'cache_dir': None},
        {'force_stepping': 1},
    ],
    ids=['uris', 'local-ammofile', 'force-stepping'],
)
def test_bfg2020_configure_prepares_stepper(tmp_path, monkeypatch, caplog, options):
    """bfg2020 runs the stepper in the tank configure, as the open source Bfg does, and the bfg2020 binary then takes
    the same stpd from the cache instead of stepping it again."""
    bfg2020 = pytest.importorskip('yandextank.plugins.Bfg2020.plugin')
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'ammo.txt').write_text('/a\n/b\n')
    cfg = dict(tank_stepper(tmp_path, 'const(10,10s)', stage=0, loop=1, **options).cfg, bfg_cmd='bfg2020')
    noop = lambda *a: None  # noqa: E731
    core = types.SimpleNamespace(
        config=types.SimpleNamespace(validated={'bfg': cfg}),
        mkstemp=lambda suffix, prefix: str(tmp_path / (prefix + suffix)),
        add_artifact_file=noop,
        artifacts_base_dir=str(tmp_path),
        resource_manager=manager,
        publish=noop,
        interrupted=threading.Event(),
    )
    plugin = bfg2020.Plugin(core, cfg, 'bfg')
    plugin.configure()
    wrapper = plugin.stepper_wrapper
    assert os.path.exists(wrapper.stpd) and os.path.exists(wrapper.stpd + '_si.json')
    assert wrapper.ammo_count == 2
    assert sum(report.Pool.from_stepper(wrapper, 'bfg', True, False, resource_manager=manager).plan().values()) == 2
    mtime = os.stat(wrapper.stpd).st_mtime_ns
    # what /usr/bin/bfg2020 does with the config the plugin wrote (bfg2020/src/cli.py, bfg.py): its own loader and
    # resource manager, the same working directory
    with open(plugin.bfg_config_file) as f:
        binary_cfg = yaml.load(f, Loader=yaml.FullLoader)
    binary = StepperWrapper(types.SimpleNamespace(resource_manager=make_resource_manager(), publish=noop), binary_cfg)
    caplog.clear()
    with caplog.at_level(logging.INFO):
        binary.read_config()
        binary.prepare_stepper()
    assert 'Using cached stpd-file' in caplog.text and 'Making stpd-file' not in caplog.text
    assert binary.stpd == wrapper.stpd and os.stat(wrapper.stpd).st_mtime_ns == mtime


def test_phantom_ipv6_target(tmp_path):
    """The stream keeps an IPv6 address without brackets: the target address puts them back before the port."""
    plugin, core = make(tmp_path, gen=phantom(stream('const(10,1m)', address='2001:db8::1', port=443)))
    assert run(plugin) == 0
    assert published(core)['target']['address'] == '[2001:db8::1]:443'


def test_bfg_stpd_file(tmp_path):
    path = stpd(tmp_path / 'ammo.stpd', [100 * i for i in range(50)])
    plugin, core = make(tmp_path, gen=bfg(path, 'stpd_file', stpd=path, uris=[], instances=10))
    assert run(plugin) == 0
    doc = published(core)
    assert doc['phases'] == [] and [w['id'] for w in doc['windows']] == ['test']
    [profile] = doc['provenance']['load_profile']['pools']
    assert (profile['schedule'], profile['ammo_sha256']) == ([], report.file_sha256(path))


def test_pause_not_shorter_than_max_wait(tmp_path, caplog):
    plugin, core = make(tmp_path, gen=generator(tmp_path, [[const(10, '10s'), const(0, '40s'), const(100, '60s')]]))
    plugin.configure()
    with caplog.at_level(logging.WARNING):
        plugin.prepare_test()
        plugin.start_test()
    shoot(plugin)
    assert plugin.post_process(0) == 0
    assert files(core) == []
    assert 'aggregator_max_wait' in caplog.text


def test_generator_prepared_after_the_section(tmp_path):
    """A section before the generator in the config: its patched config appears only by start_test."""
    gen = generator(tmp_path)
    contents, gen.config_contents = gen.config_contents, None
    plugin, core = make(tmp_path, gen=gen)
    plugin.configure()
    plugin.prepare_test()
    gen.config_contents = contents
    plugin.start_test()
    shoot(plugin)
    plugin.post_process(0)
    assert published(core)['load']['gun']['version'] == '0.8.3'


def test_h2c_taken_for_grpc_is_logged(tmp_path, caplog):
    gen = generator(tmp_path)
    gen.config_contents['pools'][0]['gun'] = {'type': 'http2', 'target': 'target:80'}
    plugin, core = make(tmp_path, gen=gen)
    plugin.configure()
    with caplog.at_level(logging.WARNING):
        plugin.prepare_test()
    assert 'target_protocol: http' in caplog.text


def test_once_pool_silent_after_its_schedule(tmp_path):
    plugin, core = make(tmp_path, gen=generator(tmp_path, [[once(1)], [const(10, '600s')]]))
    plugin.configure()
    plugin.start_test()
    shoot(plugin)
    plugin.post_process(0)
    assert [p['kind'] for p in published(core)['phases']] == ['once', 'const']


def test_hooks_never_raise(tmp_path):
    class BrokenCore(Core):
        @property
        def job(self):
            raise RuntimeError('no job')

        @job.setter
        def job(self, value):
            pass

    artifacts = tmp_path / 'artifacts'
    artifacts.mkdir()
    plugin = machine_report.Plugin(BrokenCore(artifacts, None), {}, 'machine_report')
    plugin.configure()
    plugin.prepare_test()
    plugin.start_test()
    plugin.on_aggregated_data({}, {})
    assert plugin.post_process(0) == 0
    assert os.listdir(str(artifacts)) == []


def test_pandora_version(tmp_path):
    assert report.pandora_version(stub(tmp_path)) == '0.8.3'
    pandorax = '#!/bin/sh\nprintf "Pandora X - 0.8.3.21442395\\nBased on pandora/core - 0.8.3\\n" >&2\n'
    assert report.pandora_version(stub(tmp_path, pandorax, 'pandorax')) == '0.8.3.21442395'
    assert report.pandora_version(stub(tmp_path, '#!/bin/sh\nsleep 5\n', 'slow'), timeout=0.2) is None
    assert report.pandora_version(stub(tmp_path, '#!/bin/sh\necho unknown\n', 'other')) is None
    assert report.pandora_version(str(tmp_path / 'missing')) is None


# Monitoring and generator CPU

STEP0 = load(source('tests', 'fixtures', 'monitoring', 'step0.json'))


class Solomon(object):
    """The tank Solomon plugin as the plugin sees it: by its module, panels and collector."""

    def __init__(self, panels, collector):
        self.panels, self.collector = panels, collector

    def get_option(self, name, default=None):
        return self.panels if name == 'panels' else default


Solomon.__module__ = machine_report.SOLOMON_MODULE

# the panels of step 0 with the stand selectors replaced
PANELS = {
    'target_cpu': {
        'project': 'load',
        'sensors': [
            {
                'query': 'series_sum({service="__deploy__", cluster="testing", name="cpu.usage.cores", box="target"})',
                'metric_type': 'target',
                'metric_name': 'cpu_cores',
            }
        ],
    },
    'two_named': {
        'sensors': [
            {'query': '{name="cpu.usage.cores", box="target|sidecar"}', 'metric_type': 'two', 'metric_name': 'named'}
        ]
    },
    'two_auto': {'sensors': ['{name="cpu.usage.cores", box="target|sidecar"}']},
}
SOLOMON_SECTION = {
    'monitoring': [
        {
            'kind': 'solomon',
            'host': 'target_cpu',
            'required': True,
            'metrics': [{'name': 'custom:target_cpu_cores', 'unit': 'cores'}],
        },
        {'kind': 'solomon', 'host': 'two_named', 'metrics': [{'name': 'custom:two_named', 'unit': 'cores'}]},
        {'kind': 'solomon', 'host': 'two_auto'},
    ],
    'target': {'cpu': {'source_id': 'solomon:target_cpu', 'usage_metric': 'custom:target_cpu_cores'}},
    'generator': {'dc': 'dc-a'},
}


@functools.lru_cache(maxsize=None)
def shooting_seconds(start, end):
    """Агрегированные секунды обстрела 2 rps на [start, end).

    Агрегатор танка стоит на таком обстреле около 1.2 с, а кейсы replay различаются не обстрелом, а секцией
    и данными мониторинга: считаем его один раз на окно (LOAD-3863).
    """
    rows = [(s + 0.1 + 0.5 * i, 'a', 1000, 0, 200) for s in range(start, end) for i in range(2)]
    return list(aggregate([[phout(rows)]]))


def replay(tmp_path, section, run, calls=None, collector=None, panels=PANELS, plugins=None):
    """The plugin over a shooting of 2 rps on the window [start, end) of a step-0 run (its profile: 30 s, then
    181 s) with the monitoring calls of the run in between."""
    gen = generator(tmp_path, [[const(2, '30s'), const(2, '181s')]])
    solomon = Solomon(panels, object() if collector is None else collector)
    plugin, core = make(tmp_path, section, gen=gen, plugins=dict(plugins or {}, solomon=solomon))
    plugin.configure()
    plugin.start_test()
    start, end = run['start'], run['end']
    for data in shooting_seconds(start, end):
        plugin.on_aggregated_data(data, {'ts': data['ts'], 'metrics': {'instances': 3, 'reqps': 2}})
    for call in run['calls'] if calls is None else calls:
        plugin.monitoring_data(call)
    plugin.post_process(0)
    return published(core)


def statuses(doc):
    return [(s['id'], s['status'], s['reason']) for s in doc['monitoring']['sources']]


@pytest.mark.parametrize('run', sorted(STEP0['solomon']))
def test_replay_step0_solomon(tmp_path, run):
    """Real chunks of the step-0 runs: the series_sum panel covers the test window within the tolerance, the
    panels that may pass several series are unsupported by their config, whatever their data look like."""
    doc = replay(tmp_path, SOLOMON_SECTION, STEP0['solomon'][run])
    target, named, auto = doc['monitoring']['sources']
    assert (target['status'], target['reason'], target['points']) == ('ok', None, 13)
    assert (named['status'], auto['status']) == ('unsupported', 'unsupported')
    assert 'does not aggregate all series' in named['reason'] and 'is a selector' in auto['reason']
    assert doc['statuses']['completeness'] == {'status': 'PARTIAL', 'blocking': False, 'blocking_sources': []}
    cpu = {w['window']: w for w in doc['target']['cpu']['windows']}
    assert set(cpu) == {'test', 'phase-0', 'phase-1', 'steady-1'}
    assert cpu['steady-1']['usage_cores_mean'] > 1  # the stand target at 120 rps, not the sidecar with ~0.01
    assert cpu['steady-1']['cpu_ms_per_req'] == pytest.approx(cpu['steady-1']['usage_cores_mean'] * 500)
    assert 'series' not in doc['target']['cpu']  # the option is off by default


@pytest.mark.parametrize('run', sorted(STEP0['solomon']))
def test_replay_step0_solomon_cpu_series(tmp_path, run):
    """target.cpu.series over the real chunks of the step-0 runs: the Solomon grid of 15 s covers the test window up
    to the tolerance, float ts of the panel are written as integer seconds. In bt2-bt4 the first point is a whole
    step after S, and that is no gap, as for the source."""
    section = dict(SOLOMON_SECTION, target={'cpu': dict(SOLOMON_SECTION['target']['cpu'], series=True)})
    doc = replay(tmp_path, section, STEP0['solomon'][run])
    series = doc['target']['cpu']['series']
    assert (series['status'], series['step_s'], len(series['points'])) == ('ok', 15, 13)
    test = next(w for w in doc['windows'] if w['id'] == 'test')
    assert all(test['start_ts'] <= p['ts'] < test['end_ts'] and type(p['ts']) is int for p in series['points'])
    assert doc['target']['cpu']['windows'][0]['usage_cores_mean'] == pytest.approx(
        sum(p['cores'] for p in series['points']) / 13
    )


def test_replay_step0_solomon_report_file(tmp_path):
    """The report of bt1 is a valid fixture (the Go report.Validate checks it too); it stays what the plugin
    writes, up to the fields of the machine and the moment."""
    same_as_fixture(replay(tmp_path, SOLOMON_SECTION, STEP0['solomon']['bt1']), 'plugin_solomon_step0.json')


def test_replay_step0_solomon_bad_token(tmp_path):
    """With a wrong token Solomon answers 401 and the listener gets nothing: the required source is empty."""
    doc = replay(tmp_path, SOLOMON_SECTION, STEP0['solomon']['bt1'], calls=[])
    target = statuses(doc)[0]
    assert target[:2] == ('solomon:target_cpu', 'empty') and 'a token Solomon rejects looks the same' in target[2]
    assert doc['statuses']['completeness'] == {
        'status': 'INCOMPLETE',
        'blocking': True,
        'blocking_sources': ['solomon:target_cpu'],
    }
    assert doc['target']['cpu'] is None


def test_replay_step0_solomon_no_token(tmp_path):
    """Without a token the Solomon plugin silently keeps DummyCollector: recognized by the collector type."""
    doc = replay(tmp_path, SOLOMON_SECTION, STEP0['solomon']['bt1'], collector=DummyCollector())
    assert [s[1:] for s in statuses(doc)] == [('error', 'no token: the Solomon plugin read nothing')] * 3
    assert doc['statuses']['completeness']['blocking_sources'] == ['solomon:target_cpu']
    assert doc['target']['cpu'] is None


def test_replay_step0_telegraf(tmp_path):
    """The localhost panel that YLT adds: one point a second up to 6 s before E."""
    section = {
        'monitoring': [
            {
                'kind': 'telegraf',
                'host': 'localhost',
                'entity': 'generator',
                'metrics': [
                    {'name': 'custom:cpu-cpu-total_usage_user', 'unit': 'pct'},
                    {'name': 'Memory_used', 'unit': 'bytes'},
                ],
            }
        ]
    }
    doc = replay(tmp_path, section, STEP0['telegraf'])
    [localhost] = doc['monitoring']['sources']
    assert (localhost['status'], localhost['points'], localhost['entity']) == ('ok', 206, 'generator')
    assert [m['windows'][0]['points'] for m in localhost['metrics']] == [206, 206]
    assert doc['statuses']['completeness']['status'] == 'COMPLETE'
    # the tolerance of the section: without one the last 6 s are a gap
    (tmp_path / 'strict').mkdir()
    doc = replay(tmp_path / 'strict', dict(section, monitoring_tolerance_s=0), STEP0['telegraf'])
    assert statuses(doc)[0][1:] == (
        'partial',
        'metric custom:cpu-cpu-total_usage_user: a gap of 6 s, over two '
        'median steps of 1 s; metric Memory_used: a gap of 6 s, over two median steps of 1 s',
    )


def test_monitoring_chunks_glued_and_repeated(tmp_path):
    """A Solomon panel sends a ts in a chunk per sensor; a repeated point keeps the last value."""
    section = {
        'monitoring': [
            {'kind': 'telegraf', 'host': 'h', 'metrics': [{'name': 'a', 'unit': 'none'}, {'name': 'b', 'unit': 'none'}]}
        ]
    }
    plugin, core = make(tmp_path, section)
    plugin.configure()
    plugin.start_test()
    shoot(plugin)

    def chunk(ts, **metrics):
        return {'timestamp': ts, 'data': {'h': {'comment': '', 'metrics': metrics}, 'other': {'metrics': {'a': 9}}}}

    plugin.monitoring_data([chunk(T + s, a=1) for s in range(5)] + [chunk(T + s, b=2) for s in range(5)])
    plugin.monitoring_data([chunk(T + 2, a=3)])
    plugin.monitoring_data(['not a chunk'])
    # a chunk the panel could not format comes as None: the chunks after it are kept
    plugin.monitoring_data([None, chunk(T + 4, b=5)])
    plugin.post_process(0)
    [h] = published(core)['monitoring']['sources']
    assert (h['status'], h['points']) == ('ok', 5)
    assert [m['windows'][0] for m in h['metrics']] == [
        {'window': 'test', 'points': 5, 'mean': 1.4, 'min': 1, 'max': 3},
        {'window': 'test', 'points': 5, 'mean': 2.6, 'min': 2, 'max': 5},
    ]
    assert dict(plugin._points) == {'h': {T + s: {'a': 3 if s == 2 else 1, 'b': 5 if s == 4 else 2} for s in range(5)}}


@pytest.mark.parametrize(
    'thresholds, found', [({}, [('CPU_THROTTLED', 'test')]), ({'cpu_throttled_periods_pct': 40}, [])]
)
def test_generator_cpu_from_cgroup(tmp_path, monkeypatch, thresholds, found):
    """Snapshots on the callbacks of the core and the aggregator, at least a second apart, by the monotonic clock:
    1.5 of 2 cores whatever the wall clock does. Thresholds of the section reach the signals."""
    root = tmp_path / 'cgroup'
    own_cgroup(tmp_path, monkeypatch, CGROUP_V2)
    clock, wall = [T - 1.0], [0.0]
    monkeypatch.setattr(
        machine_report, 'time', types.SimpleNamespace(time=lambda: clock[0] + wall[0], monotonic=lambda: clock[0])
    )

    def counters(t):
        stat = 'usage_usec {}\nnr_periods {}\nnr_throttled {}\nthrottled_usec {}\n'
        cgroup(root, {'cpu.stat': stat.format(int(1.5e6 * t), int(10 * t), int(3 * t), int(0.2e6 * t))})

    counters(0)
    plugin, core = make(tmp_path, {'saturation': thresholds})
    plugin.configure()
    plugin.start_test()
    wall[0] = 3600.0  # the wall clock jumps an hour ahead: snapshots do not see it
    rows = [(T + s + 0.1 * i, 'a', 1000, 0, 200) for s in range(10) for i in range(10)]
    for i, data in enumerate(aggregate([[phout(rows)]])):
        clock[0] = T + i
        counters(i + 1)
        plugin.on_aggregated_data(data, {'ts': data['ts'], 'metrics': {'instances': 3, 'reqps': 10}})
        clock[0] += 0.3  # too soon for another snapshot
        assert plugin.is_test_finished() == -1
    clock[0] = T + 10
    counters(11)
    plugin.is_test_finished()  # a second later the core callback samples too
    plugin.post_process(0)
    generator = published(core)['generator']
    assert (generator['cpu_limit_cores'], generator['cpu']['source']) == (2.0, 'cgroup_v2')
    assert len(plugin._snapshots) == 12
    test = generator['cpu']['windows'][0]
    assert test['window'] == 'test'
    assert test['usage_cores_mean'] == pytest.approx(1.5)
    assert test['util_pct_mean'] == pytest.approx(75)
    assert test['throttled_periods_pct'] == pytest.approx(30)
    assert test['throttled_cores_mean'] == pytest.approx(0.2)
    # 30 % of CFS periods throttled at 75 % of the quota: the generator is short of CPU in bursts
    assert [(s['code'], s['window']) for s in generator['saturation']['signals']] == found


def test_generator_cpu_not_from_a_foreign_cgroup(tmp_path, monkeypatch, caplog):
    own_cgroup(tmp_path, monkeypatch, dict(CGROUP_V2, **{'cgroup.procs': '1\n'}))
    plugin, core = make(tmp_path)
    plugin.configure()
    with caplog.at_level(logging.INFO):
        plugin.start_test()
    shoot(plugin)
    plugin.post_process(0)
    generator = published(core)['generator']
    assert (generator['cpu']['source'], generator['cpu_limit_cores']) == ('unavailable', None)
    assert 'does not list the tank process' in caplog.text and '0::/' in caplog.text


def solomon_target(tmp_path, caplog, section=None, panels=PANELS, plugins=None):
    with caplog.at_level(logging.WARNING):
        doc = replay(tmp_path, section or SOLOMON_SECTION, STEP0['solomon']['bt1'], panels=panels, plugins=plugins)
    return doc


def test_target_cpu_metrics_added_to_its_source(tmp_path, caplog):
    """The section names the target CPU metric only in target.cpu: the plugin reads it from the source itself."""
    monitoring = [dict(SOLOMON_SECTION['monitoring'][0], metrics=[])] + SOLOMON_SECTION['monitoring'][1:]
    doc = solomon_target(tmp_path, caplog, dict(SOLOMON_SECTION, monitoring=monitoring))
    assert doc['monitoring']['sources'][0]['status'] == 'ok'
    assert doc['target']['cpu']['windows'][0]['usage_cores_mean'] > 0


@pytest.mark.parametrize(
    'change, problem',
    [
        ({'source_id': 'solomon:typo'}, 'no monitoring source solomon:typo'),
        ({'usage_metric': 'custom:target_cpu_pct'}, 'metric custom:target_cpu_pct is in pct, not in cores'),
        (None, 'does not sum the series of the target'),
    ],
)
def test_target_cpu_that_is_not_the_whole_target(tmp_path, caplog, change, problem):
    """The plugin drops target.cpu by the config while its source is ok: the cause is in the tank log only, and the
    series option gives no series either."""
    cpu = dict(SOLOMON_SECTION['target']['cpu'], series=True)
    section, panels = dict(SOLOMON_SECTION, target={'cpu': cpu}), PANELS
    if change is None:  # the mean over pods, not their sum
        query = PANELS['target_cpu']['sensors'][0]['query'].replace('series_sum', 'series_avg')
        sensor = dict(PANELS['target_cpu']['sensors'][0], query=query)
        panels = dict(PANELS, target_cpu=dict(PANELS['target_cpu'], sensors=[sensor]))
    else:
        section = dict(SOLOMON_SECTION, target={'cpu': dict(cpu, **change)})
        if 'usage_metric' in change:
            pct = {'name': change['usage_metric'], 'unit': 'pct'}
            first = dict(SOLOMON_SECTION['monitoring'][0], metrics=[pct])
            section['monitoring'] = [first] + SOLOMON_SECTION['monitoring'][1:]
            sensor = dict(PANELS['target_cpu']['sensors'][0], metric_name='cpu_pct')
            panels = dict(PANELS, target_cpu=dict(PANELS['target_cpu'], sensors=[sensor]))
    doc = solomon_target(tmp_path, caplog, section, panels)
    assert doc['target']['cpu'] is None
    if 'usage_metric' not in (change or {}):  # the probe has no pct metric: that source is empty
        assert doc['monitoring']['sources'][0]['status'] == 'ok'
    assert 'no target CPU: ' + problem in caplog.text if change else problem in caplog.text


def test_solomon_config_errors(tmp_path, caplog):
    """A section metric that is no series of the panel and a panel in two Solomon plugins are errors."""
    monitoring = [
        dict(SOLOMON_SECTION['monitoring'][0], metrics=[{'name': 'custom:target_cpu.cores', 'unit': 'cores'}])
    ]
    doc = solomon_target(tmp_path, caplog, dict(SOLOMON_SECTION, monitoring=monitoring))
    [(_, status, reason)] = statuses(doc)
    assert status == 'error' and 'its sensors give custom:target_cpu_cores' in reason
    (tmp_path / 'two').mkdir()
    doc = solomon_target(tmp_path / 'two', caplog, plugins={'monium': Solomon(PANELS, object())})
    assert statuses(doc)[0][1:] == ('error', 'ambiguous: Solomon panel target_cpu is in several plugins')


# Inert without the section

BASE = {'core': {'artifacts_base_dir': './'}}


def packages(config):
    validated, _ = TankConfig([config], with_dynamic_options=False).validate()
    return [package for _, package, _ in validated.plugins]


def test_no_section_no_plugin():
    """The core loads a plugin only by a section with enabled and package; the base config has none."""
    assert 'machine_report' not in load_core_base_cfg()
    assert 'yandextank.plugins.MachineReport' not in packages(BASE)
    disabled = dict(BASE, machine_report={'enabled': False, 'package': 'yandextank.plugins.MachineReport'})
    assert 'yandextank.plugins.MachineReport' not in packages(disabled)


def test_section_schema():
    assert load_plugin_schema('yandextank.plugins.MachineReport')
    section = {
        'enabled': True,
        'package': 'yandextank.plugins.MachineReport',
        'pools': [{}, {'target_protocol': 'http'}],
    }
    validated, _ = TankConfig([dict(BASE, machine_report=section)], with_dynamic_options=False).validate()
    cfg = validated.validated['machine_report']
    assert (cfg['steady_trim_s'], cfg['monitoring_tolerance_s'], cfg['monitoring'], cfg['perforator']) == (
        15,
        60,
        [],
        None,
    )
    assert cfg['generator'] == {'dc_env': []}


SECTIONS = source('tests', 'fixtures', 'sections')


@pytest.mark.parametrize(
    'path',
    [
        os.path.join(verdict, name)
        for verdict in ('valid', 'invalid')
        for name in sorted(os.listdir(os.path.join(SECTIONS, verdict)))
    ],
)
def test_section_matrix(path):
    """Other validators of the section (the config validation of load testing services) check the same files and
    must reach the same verdict: the directory is the verdict."""
    with open(os.path.join(SECTIONS, path)) as f:
        config = yaml.safe_load(f)
    if path.startswith('valid'):
        TankConfig([config], with_dynamic_options=False).validate()
    else:
        with pytest.raises(ValidationError):
            TankConfig([config], with_dynamic_options=False).validate()
