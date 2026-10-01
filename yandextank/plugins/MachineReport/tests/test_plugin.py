"""The MachineReport plugin in the tank lifecycle: files it writes, what it never breaks, and that it stays inert
without its section."""

import gzip
import json
import logging
import os
import threading
import types

import pytest

from yandextank.plugins.MachineReport import plugin as machine_report
from yandextank.plugins.MachineReport import report
from yandextank.validator.validator import TankConfig, ValidationError, load_core_base_cfg, load_plugin_schema

from test_report import T, aggregate, const, once, pandora_pool, phout
from test_schema import errors, validator

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
    (tmp_path / 'cgroup').mkdir()
    (tmp_path / 'cgroup' / 'cpu.max').write_text('200000 100000')
    monkeypatch.setattr(machine_report, 'CGROUP_ROOT', str(tmp_path / 'cgroup'))
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
    monkeypatch.setenv('NODE_CLUSTER', 'vla.cluster.example')
    monkeypatch.delenv('NODE_DC', raising=False)
    section = {
        'generator': {'dc_env': ['NODE_DC', 'NODE_CLUSTER']},
        'monitoring': [
            {'kind': 'telegraf', 'host': 'target-1', 'required': True},
            {'id': 'cpu', 'kind': 'solomon', 'host': 'target_cpu', 'entity': 'target'},
        ],
        'target': {'address': 'svc:443', 'hosts': [{'host': 'pod-1', 'dc': 'sas', 'cpu_model': 'EPYC'}]},
        'perforator': {
            'microscope_id': 'm-1',
            'selector': '{service="svc"}',
            'process_comm': 'svc',
            'microscope_window': {'start_ts': T - 60, 'end_ts': T + 600},
        },
    }
    config = {
        'core': {'aggregator_max_wait': 31},
        'metaconf': {'firestarter': {'labels': {'series': 's-1', 'run': 'r-1'}, 'dc': 'sas'}},
    }
    plugin, core = make(tmp_path, section, config=config)
    plugin.configure()
    plugin.start_test()
    shoot(plugin)
    plugin.post_process(0)
    doc = published(core)
    assert [(s['id'], s['status'], s['required']) for s in doc['monitoring']['sources']] == [
        ('telegraf:target-1', 'unsupported', True),
        ('cpu', 'unsupported', False),
    ]
    assert doc['statuses']['completeness'] == {
        'status': 'INCOMPLETE',
        'blocking': True,
        'blocking_sources': ['telegraf:target-1'],
    }
    assert doc['target'] == {
        'address': 'svc:443',
        'hosts': [{'host': 'pod-1', 'dc': 'sas', 'cpu_model': 'EPYC', 'cpu_model_source': 'config'}],
        'cpu': None,
    }
    assert doc['perforator']['status'] == 'pending'
    assert doc['provenance']['labels'] == {'series': 's-1', 'run': 'r-1'}
    assert doc['provenance']['series'] == 's-1'
    assert doc['generator']['dc'] == 'vla'


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


@pytest.mark.parametrize('section', ['jmeter', 'phantom', 'bfg'])
def test_other_generators(tmp_path, section):
    plugin, core = make(tmp_path, gen=generator(tmp_path, section=section))
    plugin.configure()
    plugin.start_test()
    shoot(plugin)
    assert plugin.post_process(0) == 0
    assert files(core) == []


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


def test_cgroup_log(tmp_path, caplog):
    (tmp_path / 'cgroup.controllers').write_text('cpu')
    (tmp_path / 'cpu.max').write_text('200000 100000')
    (tmp_path / 'cpu.stat').write_text('usage_usec 10\nnr_periods 5\nnr_throttled 2\nthrottled_usec 7\n')
    with caplog.at_level(logging.INFO):
        machine_report.log_cgroup('start', str(tmp_path))
        machine_report.log_cgroup('end', str(tmp_path / 'missing'))
    assert "version v2" in caplog.text and 'limit 2.0 cores' in caplog.text and "'nr_throttled': '2'" in caplog.text


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
    for bad in (
        {'unknown': 1},
        {'pools': [{'target_protocol': 'h3'}]},
        {'monitoring': [{'kind': 'telegraf'}]},
        {'generator': {'dc_env': ['']}},
    ):
        with pytest.raises(ValidationError):
            TankConfig([dict(BASE, machine_report=dict(section, **bad))], with_dynamic_options=False).validate()
