import glob
import logging
import os
import threading

import pytest
import sys

import shutil
import yaml
from queue import Queue
from unittest import mock

from yandextank.common import monitoring
from yandextank.common.exceptions import GeneratorNotFound
from yandextank.common.interfaces import MonitoringPlugin
from yandextank.common.monitoring import DefaultCollector, MonitoringPanel
from yandextank.core import TankCore
from yandextank.core.tankcore import Job
from yandextank.core.tankworker import parse_options, TankInfo
from yandextank.stepper.module_exceptions import DiskLimitError

try:
    from yatest import common

    PATH = common.source_path('load/projects/yandex-tank/yandextank/core/tests')
    TMPDIR = os.path.join(os.getcwd(), 'artifacts_dir')
except ImportError:
    PATH = os.path.dirname(__file__)
    TMPDIR = './'

logger = logging.getLogger('')
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler(sys.stdout)
fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s %(filename)s:%(lineno)d\t%(message)s")
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(fmt)
logger.addHandler(console_handler)


def load_yaml(directory, filename):
    with open(os.path.join(directory, filename), 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)


CFG1 = {
    "version": "1.8.36",
    "core": {'operator': 'fomars', 'artifacts_base_dir': TMPDIR, 'artifacts_dir': TMPDIR},
    'telegraf': {
        'package': 'yandextank.plugins.Telegraf',
        'enabled': True,
        'config': 'test_monitoring.xml',
        'disguise_hostnames': True,
    },
    'phantom': {
        'package': 'yandextank.plugins.Phantom',
        'enabled': True,
        'address': 'localhost',
        'header_http': '1.1',
        'uris': ['/'],
        'load_profile': {'load_type': 'rps', 'schedule': 'line(1, 10, 1m)'},
        'phantom_path': './phantom_mock.sh',
        'connection_test': False,
    },
    'lunapark': {
        'package': 'yandextank.plugins.DataUploader',
        'enabled': True,
        'api_address': 'https://lunapark.test.yandex-team.ru/',
        'task': 'LOAD-204',
        'ignore_target_lock': True,
        # В сборке сети нет, а по умолчанию аплоадер ждёт её 10 попыток по 60 с
        # (maintenance_attempts x maintenance_timeout) — это и есть те 600 с,
        # из-за которых тест не влезал в SMALL-чанк (LOAD-3541).
        'maintenance_attempts': 1,
        'maintenance_timeout': 1,
        'network_attempts': 1,
        'network_timeout': 1,
        'api_attempts': 1,
        'api_timeout': 1,
        'connection_timeout': 1,
    },
}

CFG2 = {
    "version": "1.8.36",
    "core": {'operator': 'fomars', 'artifacts_base_dir': TMPDIR, 'artifacts_dir': TMPDIR},
    'telegraf': {
        'enabled': False,
    },
    'phantom': {
        'package': 'yandextank.plugins.Phantom',
        'enabled': True,
        'address': 'lunapark.test.yandex-team.ru',
        'header_http': '1.1',
        'uris': ['/'],
        'load_profile': {'load_type': 'rps', 'schedule': 'line(1, 10, 1m)'},
        'connection_test': False,
    },
    'lunapark': {
        'package': 'yandextank.plugins.DataUploader',
        'enabled': True,
        'api_address': 'https://lunapark.test.yandex-team.ru/',
        'task': 'LOAD-204',
        'ignore_target_lock': True,
    },
    'shellexec': {'enabled': False},
}

CFG_LARGE_STEPPER = {
    "version": "1.8.36",
    "core": {'operator': 'fomars', 'artifacts_base_dir': TMPDIR, 'artifacts_dir': TMPDIR},
    'phantom': {
        'package': 'yandextank.plugins.Phantom',
        'enabled': True,
        'address': 'localhost',
        'header_http': '1.1',
        'uris': ['/'],
        'load_profile': {'load_type': 'rps', 'schedule': 'const(9,999999999h)'},
        'phantom_path': './phantom_mock.sh',
        'connection_test': False,
    },
}

CFG_SMALL_STEPPER = {
    "version": "1.8.36",
    "core": {'operator': 'fomars', 'artifacts_base_dir': TMPDIR, 'artifacts_dir': TMPDIR},
    'phantom': {
        'package': 'yandextank.plugins.Phantom',
        'enabled': True,
        'address': 'localhost',
        'header_http': '1.1',
        'uris': ['/'],
        'load_profile': {'load_type': 'rps', 'schedule': 'const(1,1m)'},
        'phantom_path': './phantom_mock.sh',
        'connection_test': False,
    },
}

CFG_WITHOUT_GEN = {
    "version": "1.8.36",
    "core": {'operator': 'fomars', 'artifacts_base_dir': TMPDIR, 'artifacts_dir': TMPDIR},
    'phantom': {'package': 'yandextank.plugins.Phantom', 'enabled': False},
    'lunapark': {
        'package': 'yandextank.plugins.DataUploader',
        'enabled': True,
        'api_address': 'https://lunapark.test.yandex-team.ru/',
        'task': 'LOAD-204',
        'ignore_target_lock': True,
    },
}

CFG_MULTI = load_yaml(PATH, 'test_multi_cfg.yaml')
# Каталог артефактов задаём здесь, а не в yaml: TMPDIR вычисляется по окружению.
# Без него танк создаёт каталог по умолчанию, а в песочнице автосборки это падает
# на os.makedirs (LOAD-3541).
CFG_MULTI['core']['artifacts_base_dir'] = TMPDIR
CFG_MULTI['core']['artifacts_dir'] = TMPDIR

original_working_dir = os.getcwd()


def setup_module(module):
    os.chdir(PATH)


@pytest.mark.parametrize(
    'config, expected',
    [
        (
            CFG1,
            {
                'plugin_telegraf',
                'plugin_phantom',
                'plugin_lunapark',
                'plugin_rcheck',
                'plugin_shellexec',
                'plugin_autostop',
                'plugin_console',
                'plugin_rcassert',
                'plugin_json_report',
            },
        ),
        (
            CFG2,
            {
                'plugin_phantom',
                'plugin_lunapark',
                'plugin_rcheck',
                'plugin_autostop',
                'plugin_console',
                'plugin_rcassert',
                'plugin_json_report',
            },
        ),
    ],
)
def test_core_load_plugins(config, expected):
    core = TankCore(
        [load_yaml(os.path.join(PATH, '../config'), '00-base.yaml'), config], threading.Event(), TankInfo({})
    )
    try:
        core.load_plugins()
        assert set(core.plugins.keys()) == expected
    finally:
        core.close()


def test_core_load_plugins_without_gen():
    core = TankCore([CFG_WITHOUT_GEN], threading.Event(), TankInfo({}))
    with pytest.raises(GeneratorNotFound):
        core.load_plugins()


def test_core_plugins_configure():
    core = TankCore([CFG1], threading.Event(), TankInfo({}))
    core.plugins_configure()


def test_small_stepper_file():
    core = TankCore([CFG_SMALL_STEPPER], threading.Event(), TankInfo({}))
    core.plugins_configure()


def test_large_stepper_file():
    core = TankCore([CFG_LARGE_STEPPER], threading.Event(), TankInfo({}))
    with pytest.raises(DiskLimitError):
        core.plugins_configure()


@pytest.mark.parametrize('config, expected', [(CFG1, None), (CFG_MULTI, None)])
def test_plugins_prepare_test(config, expected):
    core = TankCore([config], threading.Event(), TankInfo({}))
    core.plugins_prepare_test()


@pytest.mark.parametrize(
    'config',
    [
        CFG_MULTI,
    ],
)
def test_start_test(config):
    core = TankCore([config], threading.Event(), TankInfo({}))
    core.plugins_prepare_test()
    core.plugins_start_test()
    core.plugins_end_test(1)


class _EndTestRecorder:
    def __init__(self, name, calls):
        self.name, self.calls = name, calls

    def end_test(self, retcode):
        self.calls.append(self.name)
        return retcode


class _FakeClock:
    """Stands in for `time` in yandextank.common.monitoring: sleep() only advances virtual time."""

    def __init__(self):
        self.sleeps = []

    def sleep(self, seconds):
        self.sleeps.append(seconds)

    def time(self):
        return sum(self.sleeps)

    monotonic = time


def _bare_core(plugins, monitorings, generator, aggregator):
    core = TankCore.__new__(TankCore)  # no config validation, no artifacts dir
    core.info = TankInfo({})
    core.interrupted = threading.Event()
    core.resource_manager = None
    core.monitoring_data_listeners = []
    core._plugins = plugins
    core._job = Job(monitoring_plugins=monitorings, aggregator=aggregator, tank='tank', generator_plugin=generator)
    return core


def test_plugins_end_test_calls_each_plugin_once():
    calls = []
    gen, mon, other = (_EndTestRecorder(name, calls) for name in ('gen', 'mon', 'other'))
    aggregator = mock.Mock(end_test=gen.end_test)  # TankAggregator.end_test stops the generator
    core = _bare_core({'plugin_gen': gen, 'plugin_mon': mon, 'plugin_other': other}, [mon], gen, aggregator)

    assert core.plugins_end_test(0) == 0
    assert calls == ['gen', 'mon', 'other']


def test_plugins_end_test_monitoring_stop_duration():
    # Solomon defaults: timeout = poll_interval = 30 s. One DefaultCollector.stop is
    # 31 s grace sleep + 30 s panel drain = 61 s; a second end_test used to add 31 s more.
    clock = _FakeClock()
    core = _bare_core({}, [], None, mock.Mock(end_test=lambda rc: rc))
    mon = MonitoringPlugin(core, {}, 'solomon')
    mon.collector = DefaultCollector(logger=logger, timeout=30, poll_interval=30)
    mon.collector.add_sensor(mock.Mock())
    mon.collector.add_panel(MonitoringPanel('panel', 30, Queue()))
    core._plugins['plugin_solomon'] = mon
    core.job.monitoring_plugins.append(mon)

    with mock.patch.object(monitoring, 'time', clock):
        mon.start_test()
        core.plugins_end_test(0)

    assert clock.time() == 61


@pytest.mark.parametrize(
    'options, expected',
    [
        (
            [
                'meta.task=LOAD-204',
                'phantom.ammofile = air-tickets-search-ammo.log',
                'meta.component = air_tickets_search [imbalance]',
                'meta.jenkinsjob = https://jenkins-load.yandex-team.ru/job/air_tickets_search/',
            ],
            [
                {'uploader': {'package': 'yandextank.plugins.DataUploader', 'task': 'LOAD-204'}},
                {'phantom': {'package': 'yandextank.plugins.Phantom', 'ammofile': 'air-tickets-search-ammo.log'}},
                {
                    'uploader': {
                        'package': 'yandextank.plugins.DataUploader',
                        'component': 'air_tickets_search [imbalance]',
                    }
                },
                {
                    'uploader': {
                        'package': 'yandextank.plugins.DataUploader',
                        'meta': {'jenkinsjob': 'https://jenkins-load.yandex-team.ru/job/air_tickets_search/'},
                    }
                },
            ],
        ),
        #     with converting/type-casting
        (
            ['phantom.rps_schedule = line(10,100,10m)', 'phantom.instances=200', 'phantom.connection_test=0'],
            [
                {
                    'phantom': {
                        'package': 'yandextank.plugins.Phantom',
                        'load_profile': {'load_type': 'rps', 'schedule': 'line(10,100,10m)'},
                    }
                },
                {'phantom': {'package': 'yandextank.plugins.Phantom', 'instances': 200}},
                {'phantom': {'package': 'yandextank.plugins.Phantom', 'connection_test': 0}},
            ],
        ),
    ],
)
def test_parse_options(options, expected):
    assert parse_options(options) == expected


def teardown_module(module):
    for pattern in ['monitoring_*.xml', 'agent_*', '*.log', '*.stpd_si.json', '*.stpd', '*.conf']:
        for path in glob.glob(pattern):
            os.remove(path)
    try:
        shutil.rmtree('logs/')
        shutil.rmtree('lunapark/')
    except OSError:
        pass
    os.chdir(original_working_dir)


def sort_schema_alphabetically(filename):
    with open(filename, 'r') as f:
        schema = yaml.load(f, Loader=yaml.FullLoader)
    with open(filename, 'w') as f:
        for key, value in sorted(schema.items()):
            f.write(key + ':\n')
            for k, v in sorted(value.items()):
                f.write('  ' + k + ': ' + str(v).lower() + '\n')
