import ConfigParser
import os

import yaml
import pytest

from yandextank.config_converter.converter import convert_ini, parse_package_name, parse_sections, combine_sections
from yandextank.core.consoleworker import load_core_base_cfg, cfg_folder_loader, load_cfg
from yandextank.validator.validator import TankConfig


@pytest.mark.parametrize('ini_file, expected', [
    ('test_config1.ini',
     {
         'phantom': [
             ('address', 'load.example.net'),
             ('load_profile', {'load_type': 'rps', 'schedule': 'step(50,900,5,5)'}),
             ('instances', 1000),
             ('header_http', '1.1'),
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
         'uploader': [
             ('api_address', 'https://lunapark.yandex-team.ru/'),
             ('task', 'LOAD-204'),
             ('operator', 'fomars'),
             ('job_name', '[1495714217] [api_v2] portal-morda-conf=2017.05.25-0'),
             ('lock_targets', 'auto'),
         ],
         'aggregator': [],
         'telegraf': [
             ('config', 'monitoring1.xml'),
             ('default_target', 'localhost'),
             ('ssh_timeout', '5s'),
         ]
     }
     ),
    (
        'test_config2.ini',
        {
            'uploader': [
                ('task', 'MAPSJAMS-1946'),
                ('ignore_target_lock', True),
                ('api_address', 'https://lunapark.yandex-team.ru/'),
            ],
            'aggregator': [],
            'phantom': [
                ('load_profile', {'load_type': 'rps', 'schedule': 'line(1,6000,20m)'}),
                ('instances', 10000),
                ('autocases', '0'),
                ('address', 'foo.example.net'),
                ('port', '80'),
            ],
            'phantom-1': [
                ('ammofile',
                 '/var/bmpt-data/goods/ligreen/projects/regress/analyser-usershandler/get-segmentshandler.ammo'),
                ('load_profile', {'load_type': 'rps', 'schedule': 'const(0.2,20m)'}),
                ('instances', 10),
                ('address', 'foo.example.org'),
                ('autocases', '1'),
            ],
            'telegraf': [
                ('config', 'monitoring.xml'),
            ],
            'autostop': [
                ('autostop', '''quantile(50,20,30s)
http(4xx,50%,5)
http(5xx,5%,4)
net(1xx,10,5)
net(43,10,5)
metric_higher(foo.example.net,group1_usershandler-average-task-age,3,70)''')
            ]
        }
    ),
])
def test_parse_sections(ini_file, expected):
    cfg_ini = ConfigParser.ConfigParser()
    cfg_ini.read(os.path.join(os.path.dirname(__file__), ini_file))
    assert {section.name: section.options for section in parse_sections(cfg_ini)} == expected


@pytest.mark.parametrize('ini_file, expected', [
    (
        'test_config2.ini',
        {
            'uploader': [
                ('task', 'MAPSJAMS-1946'),
                ('ignore_target_lock', True),
                ('api_address', 'https://lunapark.yandex-team.ru/'),
            ],
            'aggregator': [],
            'phantom': [
                ('load_profile', {'load_type': 'rps', 'schedule': 'line(1,6000,20m)'}),
                ('instances', 10000),
                ('autocases', '0'),
                ('address', 'foo.example.net'),
                ('port', '80'),
                ('multi', [{
                    'ammofile': '/var/bmpt-data/goods/ligreen/projects/regress/analyser-usershandler/get-segmentshandler.ammo',
                    'load_profile': {'load_type': 'rps', 'schedule': 'const(0.2,20m)'},
                    'instances': 10,
                    'address': 'foo.example.org',
                    'autocases': '1'}])
            ],
            'telegraf': [
                ('config', 'monitoring.xml'),
            ],
            'autostop': [
                ('autostop', '''quantile(50,20,30s)
http(4xx,50%,5)
http(5xx,5%,4)
net(1xx,10,5)
net(43,10,5)
metric_higher(foo.example.net,group1_usershandler-average-task-age,3,70)''')
            ]
        }
    )
])
def test_combine_sections(ini_file, expected):
    cfg_ini = ConfigParser.ConfigParser()
    cfg_ini.read(os.path.join(os.path.dirname(__file__), ini_file))
    assert {section.name: section.options for section in combine_sections(parse_sections(cfg_ini))} == expected


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
    ('test_config3.ini', 'test_config3.yaml'),
    ('test_config4.ini', 'test_config4.yaml')
])
def test_convert_ini_phantom(ini_file, yaml_file):
    with open(os.path.join(os.path.dirname(__file__), yaml_file), 'r') as f:
        assert convert_ini(os.path.join(os.path.dirname(__file__), ini_file)) == yaml.load(f)


@pytest.mark.parametrize('ini_file', [
    'test_config1.ini',
    'test_config2.ini',
    'test_config3.ini',
    'test_config4.ini',
])
def test_validate(ini_file):
    # noinspection PyStatementEffect
    TankConfig([load_core_base_cfg()] +
               cfg_folder_loader(os.path.join(os.path.dirname(__file__), 'etc_cfg')) +
               [load_cfg(os.path.join(os.path.dirname(__file__), ini_file))]).validated
