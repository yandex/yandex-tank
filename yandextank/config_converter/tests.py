import ConfigParser

import yaml
import pytest

from config_converter import convert_ini, parse_package_name, parse_sections


@pytest.mark.parametrize('ini_file, expected', [
    ('test_config1.ini',
     {
         'phantom': [
             ('address', 'load.wfront.yandex.net'),
             ('load_profile', {'load_type': 'rps', 'schedule': 'step(50,900,5,5)'}),
             ('instances', 1000),
             ('header_http', '1.1'),
             ('ammofile', 'ammo'),
             ('threads', 17),
             ('tank_type', 'http'),
             ('ammo_type', 'phantom'),
             ('loop', -1),
             ('ammo_limit', -1),
             ('enum_ammo', False),
             ('use_caching', True),
             ('file_cache', 8192),
             ('force_stepping', 0),
             ('connection_test', False),
             ('uris', '/'),
         ],
         'meta': [
             ('api_address', 'https://lunapark.yandex-team.ru/'),
             ('task', 'HOME-37260'),
             ('operator', 'cheetah'),
             ('job_name', '[1495714217] [api_v2] portal-morda-conf=2017.05.25-0'),
             ('lock_targets', 'auto'),
         ],
         'aggregator': [
             ('precise_cumulative', 0),
             ('time_periods',
              '1ms 2 3 4 5 6 7 8 9 10 20 30 40 50 60 70 80 90 100 150 200 250 300 350 400 450 500 600 650 700 750 800 850 900 950 1s 1500 2s 2500 3s 3500 4s 4500 5s 5500 6s 6500 7s 7500 8s 8500 9s 9500 10s 11s'),
         ],
         'monitoring': [
             ('config', 'monitoring.xml'),
             ('default_target', 'localhost'),
             ('ssh_timeout', '5s'),
         ]
     }
     ),
])
def test_parse_sections(ini_file, expected):
    cfg_ini = ConfigParser.ConfigParser()
    cfg_ini.read(ini_file)
    assert {section.name: section.options for section in parse_sections(cfg_ini)} == expected


@pytest.mark.parametrize('package_path, expected', [
    ('Tank/Plugins/Aggregator.py', 'Aggregator'),
    ('Tank/Plugins/Overload.py', 'DataUploader'),
    ('yandextank.plugins.Overload', 'DataUploader'),
    ('yatank_internal.plugins.DataUploader', 'DataUploader'),
    ('yandextank.plugins.Console', 'Console')
])
def test_parse_package(package_path, expected):
    assert parse_package_name(package_path) == expected


@pytest.mark.parametrize('ini_file, yaml_file', [
    ('test_config1.ini', 'test_config1.yaml'),
    ('test_config2.ini', 'test_config2.yaml'),
    ('test_config3.ini', 'test_config3.yaml')
])
def test_convert_ini_phantom(ini_file, yaml_file):
    with open(yaml_file, 'r') as f:
        assert convert_ini(ini_file) == yaml.load(f)


        # def test_disable_plugin():
        #     raise NotImplementedError
