import ConfigParser
import os

import yaml
import pytest

from yandextank.config_converter.converter import convert_ini, parse_package_name, parse_sections, combine_sections, \
    convert_single_option, OptionsConflict
from yandextank.core.consoleworker import load_core_base_cfg, cfg_folder_loader, load_cfg
from yandextank.validator.validator import TankConfig


@pytest.mark.parametrize('ini_file, expected', [
    ('test_config1.ini',
     {'phantom': 'Phantom', 'telegraf': 'Telegraf', 'meta': 'DataUploader'}),
    ('test_config2.ini',
     {'phantom': 'Phantom', 'telegraf': 'Telegraf', 'phantom-1': 'Phantom',
      'meta': 'DataUploader', 'autostop': 'Autostop'}),
])
def test_parse_sections(ini_file, expected):
    cfg_ini = ConfigParser.ConfigParser()
    cfg_ini.read(os.path.join(os.path.dirname(__file__), ini_file))
    assert {section.name: section.plugin for section in parse_sections(cfg_ini)} == expected


@pytest.mark.parametrize('ini_file, expected', [
    (
        'test_config2.ini',
        {
            'meta': {
                'ignore_target_lock': True,
                'task': 'MAPSJAMS-1946',
                'api_address': 'https://lunapark.yandex-team.ru/'},
            'phantom': {
                'load_profile': {'load_type': 'rps', 'schedule': 'line(1,6000,20m)'},
                'autocases': 0,
                'multi': [
                    {'ammofile': '/var/bmpt-data/goods/ligreen/projects/regress/analyser-usershandler/get-segmentshandler.ammo',
                     'instances': 10,
                     'load_profile': {'load_type': 'rps', 'schedule': 'const(0.2,20m)'},
                     'autocases': 1,
                     'address': 'foo.example.org'}],
                'instances': 10000,
                'address': 'foo.example.net',
                'port': '80'},
            'telegraf': {'config': 'monitoring.xml'},
            'autostop': {'autostop': [
                'quantile(50,20,30s)',
                'http(4xx,50%,5)',
                'http(5xx,5%,4)',
                'net(1xx,10,5)',
                'net(43,10,5)',
                'metric_higher(foo.example.net,group1_usershandler-average-task-age,3,70)'
            ]
            }
        })])
def test_combine_sections(ini_file, expected):
    cfg_ini = ConfigParser.ConfigParser()
    cfg_ini.read(os.path.join(os.path.dirname(__file__), ini_file))
    assert {section.name: section.merged_options for section in combine_sections(parse_sections(cfg_ini))} == expected


@pytest.mark.parametrize('package_path, expected', [
    ('Tank/Plugins/Aggregator.py', 'Aggregator'),
    ('Tank/Plugins/Overload.py', 'DataUploader'),
    ('yandextank.plugins.Overload', 'DataUploader'),
    ('yatank_internal.plugins.DataUploader', 'DataUploader'),
    ('yandextank.plugins.Console', 'Console')
])
def test_parse_package(package_path, expected):
    assert parse_package_name(package_path) == expected


# TODO: get test configs list automatically
@pytest.mark.parametrize('ini_file, yaml_file', [
    ('test_config1.ini', 'test_config1.yaml'),
    ('test_config2.ini', 'test_config2.yaml'),
    ('test_config3.ini', 'test_config3.yaml'),
    ('test_config4.ini', 'test_config4.yaml'),
    ('test_config5.ini', 'test_config5.yaml'),
    ('test_config5.1.ini', 'test_config5.1.yaml'),
    ('test_config6.ini', 'test_config6.yaml'),
    ('test_config7.ini', 'test_config7.yaml'),
    ('test_config8.ini', 'test_config8.yaml'),
    ('test_config9.ini', 'test_config9.yaml'),
    ('test_config10.ini', 'test_config10.yaml'),
    ('test_config11.ini', 'test_config11.yaml'),
    ('test_config12.ini', 'test_config12.yaml'),
    ('test_config13.ini', 'test_config13.yaml'),
])
def test_convert_ini_phantom(ini_file, yaml_file):
    with open(os.path.join(os.path.dirname(__file__), yaml_file), 'r') as f:
        assert convert_ini(os.path.join(os.path.dirname(__file__), ini_file)) == yaml.load(f, Loader=yaml.FullLoader)


@pytest.mark.parametrize('ini_file, msgs', [
    ('test_config2.1.ini', ['stpd_file', 'rps_schedule'])
])
def test_conflict_opts(ini_file, msgs):
    with pytest.raises(OptionsConflict) as e:
        convert_ini(os.path.join(os.path.dirname(__file__), ini_file))
    assert all([msg in e.value.message for msg in msgs])


@pytest.mark.parametrize('ini_file', [
    'test_config1.ini',
    'test_config2.ini',
    'test_config3.ini',
    'test_config4.ini',
    'test_config5.ini',
    'test_config6.ini',
    'test_config7.ini',
    'test_config10.yaml',
    'test_config11.yaml',
    'test_config12.ini',
])
def test_validate(ini_file):
    # noinspection PyStatementEffect
    TankConfig([load_core_base_cfg()]
               + cfg_folder_loader(os.path.join(os.path.dirname(__file__), 'etc_cfg'))
               + [load_cfg(os.path.join(os.path.dirname(__file__), ini_file))]).validated


@pytest.mark.parametrize('key, value, expected', [
    ('phantom.uris', '/',
     {'phantom': {'package': 'yandextank.plugins.Phantom', 'uris': ['/']}}),
    ('tank.plugin_uploader', 'yandextank.plugins.DataUploader',
     {'uploader': {'enabled': True, 'package': 'yandextank.plugins.DataUploader'}}),
    ('phantom.rps_schedule', 'line(1,10)',
     {'phantom': {
         'load_profile': {'load_type': 'rps', 'schedule': 'line(1,10)'},
         'package': 'yandextank.plugins.Phantom'}}),
    ('bfg.gun_config.module_name', 'bayan_load',
     {'bfg': {'package': 'yandextank.plugins.Bfg', 'gun_config': {'module_name': 'bayan_load'}}})
])
def test_convert_single_option(key, value, expected):
    assert convert_single_option(key, value) == expected
