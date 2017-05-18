import glob
import logging
import os

import pytest
import sys
import yaml

from yandextank.core import TankCore

logger = logging.getLogger('')
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler(sys.stdout)
fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s %(filename)s:%(lineno)d\t%(message)s")
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(fmt)
logger.addHandler(console_handler)


def load_yaml(directory, filename):
    with open(os.path.join(directory, filename), 'r') as f:
        return yaml.load(f)


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
        'address': 'lunapark.test.yandex-team.ru',
        'header_http': '1.1',
        'uris': '/',
        'load_profile': {'load_type': 'rps', 'schedule': 'line(1, 10, 1m)'}
    },
    'lunapark': {
        'package': 'yandextank.plugins.DataUploader',
        'enabled': True,
        'api_address': 'https://lunapark.test.yandex-team.ru/',
        'copy_config_to': 'test_config_copy.yaml'
    },
    'overload': {
        'package': 'yandextank.plugins.DataUploader',
        'enabled': True,
        'api_address': 'https://overload.yandex.net/',
        'token_file': '/Users/fomars/dev/yandex-tank/tmp/token.txt'
    },
    'aggregator': {
        'package': 'yandextank.plugins.Aggregator',
        'enabled': True,
        'verbose_histogram': True
    }
}

CFG_MULTI = load_yaml('./', 'test_multi_cfg.yaml')


@pytest.mark.parametrize('config, expected', [
    (CFG1,
     {'plugin_telegraf', 'plugin_phantom', 'plugin_lunapark', 'plugin_overload', 'plugin_aggregator'})
])
def test_core_load_plugins(config, expected):
    core = TankCore(configs=[config])
    core.load_plugins()
    assert set(core.plugins.keys()) == expected


@pytest.mark.parametrize('config, expected', [
    (CFG1, None)
])
def test_core_plugins_configure(config, expected):
    core = TankCore(configs=[config])
    core.plugins_configure()


@pytest.mark.parametrize('config, expected', [
    (CFG1, None),
    (CFG_MULTI, None)
])
def test_plugins_prepare_test(config, expected):
    core = TankCore(configs=[config])
    core.plugins_prepare_test()


def test_stpd_file():
    raise NotImplementedError

@pytest.mark.parametrize('config', [
    CFG1,
    CFG_MULTI,
])
def test_start_test(config):
    core = TankCore(configs=[config])
    core.plugins_prepare_test()
    core.plugins_start_test()


def teardown_module(module):
    for pattern in ['monitoring_*.xml', 'agent_*', '*.log', '*.stpd_si.json', '*.stpd', '*.conf']:
        for path in glob.glob(pattern):
            os.remove(path)


def sort_schema_alphabetically(filename):
    with open(filename, 'r') as f:
        schema = yaml.load(f)
    with open(filename, 'w') as f:
        for key in sorted(schema.keys()):
            f.write(key + ':\n')
            for attr in schema[key].keys():
                f.write('  ' + attr + ': ' + str(schema[key][attr]).lower() + '\n')