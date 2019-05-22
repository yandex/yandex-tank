import glob
import logging
import os
import threading

import pytest
import sys

import shutil
import yaml

from yandextank.core import TankCore
from yandextank.core.consoleworker import parse_options

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
    "core": {
        'operator': 'fomars',
        'artifacts_base_dir': './',
        'artifacts_dir': './'
    },
    'telegraf': {
        'package': 'yandextank.plugins.Telegraf',
        'enabled': True,
        'config': 'test_monitoring.xml',
        'disguise_hostnames': True
    },
    'phantom': {
        'package': 'yandextank.plugins.Phantom',
        'enabled': True,
        'address': 'lunapark.yandex-team.ru',
        'header_http': '1.1',
        'uris': ['/'],
        'load_profile': {'load_type': 'rps', 'schedule': 'line(1, 10, 1m)'},
        'phantom_path': './phantom_mock.sh',
        'connection_test': False
    },
    'lunapark': {
        'package': 'yandextank.plugins.DataUploader',
        'enabled': True,
        'api_address': 'https://lunapark.test.yandex-team.ru/',
        'task': 'LOAD-204',
        'ignore_target_lock': True,
    }
}

CFG2 = {
    "version": "1.8.36",
    "core": {
        'operator': 'fomars',
        'artifacts_base_dir': './',
        'artifacts_dir': './'
    },
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
        'connection_test': False
    },
    'lunapark': {
        'package': 'yandextank.plugins.DataUploader',
        'enabled': True,
        'api_address': 'https://lunapark.test.yandex-team.ru/',
        'task': 'LOAD-204',
        'ignore_target_lock': True,
    },
    'shellexec': {
        'enabled': False
    }
}

CFG_MULTI = load_yaml(os.path.dirname(__file__), 'test_multi_cfg.yaml')
original_working_dir = os.getcwd()


def setup_module(module):
    os.chdir(os.path.dirname(__file__))


@pytest.mark.parametrize('config, expected', [
    (CFG1,
     {'plugin_telegraf', 'plugin_phantom', 'plugin_lunapark',
      'plugin_rcheck', 'plugin_shellexec', 'plugin_autostop',
      'plugin_console', 'plugin_rcassert', 'plugin_json_report',
      }),
    (CFG2,
     {'plugin_phantom', 'plugin_lunapark', 'plugin_rcheck',
      'plugin_autostop', 'plugin_console',
      'plugin_rcassert', 'plugin_json_report',
      }
     )
])
def test_core_load_plugins(config, expected):
    core = TankCore([load_yaml(os.path.join(os.path.dirname(__file__), '../config'), '00-base.yaml'), config],
                    threading.Event())
    core.load_plugins()
    assert set(core.plugins.keys()) == expected


@pytest.mark.parametrize('config, expected', [
    (CFG1, None)
])
def test_core_plugins_configure(config, expected):
    core = TankCore([config], threading.Event())
    core.plugins_configure()


@pytest.mark.skip('disabled for travis')
@pytest.mark.parametrize('config, expected', [
    (CFG1, None),
    (CFG_MULTI, None)
])
def test_plugins_prepare_test(config, expected):
    core = TankCore([config], threading.Event())
    core.plugins_prepare_test()


@pytest.mark.skip('Not implemented')
def test_stpd_file():
    raise NotImplementedError


@pytest.mark.skip('disabled for travis')
@pytest.mark.parametrize('config', [
    CFG_MULTI,
])
def test_start_test(config):
    core = TankCore(configs=[config])
    core.plugins_prepare_test()
    core.plugins_start_test()
    core.plugins_end_test(1)


@pytest.mark.parametrize('options, expected', [
    (
        ['meta.task=LOAD-204',
         'phantom.ammofile = air-tickets-search-ammo.log',
         'meta.component = air_tickets_search [imbalance]',
         'meta.jenkinsjob = https://jenkins-load.yandex-team.ru/job/air_tickets_search/'],
        [{'uploader': {'package': 'yandextank.plugins.DataUploader', 'task': 'LOAD-204'}},
         {'phantom': {'package': 'yandextank.plugins.Phantom', 'ammofile': 'air-tickets-search-ammo.log'}},
         {'uploader': {'package': 'yandextank.plugins.DataUploader', 'component': 'air_tickets_search [imbalance]'}},
         {'uploader': {'package': 'yandextank.plugins.DataUploader',
                       'meta': {'jenkinsjob': 'https://jenkins-load.yandex-team.ru/job/air_tickets_search/'}}}]
    ),
    #     with converting/type-casting
    (
        ['phantom.rps_schedule = line(10,100,10m)',
         'phantom.instances=200',
         'phantom.connection_test=0'],
        [{'phantom': {'package': 'yandextank.plugins.Phantom', 'load_profile': {'load_type': 'rps', 'schedule': 'line(10,100,10m)'}}},
         {'phantom': {'package': 'yandextank.plugins.Phantom', 'instances': 200}},
         {'phantom': {'package': 'yandextank.plugins.Phantom', 'connection_test': 0}}]
    )
])
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
    global original_working_dir
    os.chdir(original_working_dir)


def sort_schema_alphabetically(filename):
    with open(filename, 'r') as f:
        schema = yaml.load(f, Loader=yaml.FullLoader)
    with open(filename, 'w') as f:
        for key in sorted(schema.keys()):
            f.write(key + ':\n')
            for attr in schema[key].keys():
                f.write('  ' + attr + ': ' + str(schema[key][attr]).lower() + '\n')
