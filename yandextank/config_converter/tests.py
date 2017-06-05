import yaml
import pytest

from config_converter import convert_ini, parse_package_name


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
    ('test_config1.ini', 'test_config1.yaml')
])
def test_convert_ini_phantom(ini_file, yaml_file):
    with open(yaml_file, 'r') as f:
        assert convert_ini(ini_file) == yaml.load(f)


def test_disable_plugin():
    raise NotImplementedError