import pytest
from yandextank.plugins.DataUploader.cli import from_tank_config, get_logger


@pytest.mark.parametrize('test_dir, expected', [
    ('yandextank/plugins/DataUploader/tests/test_postloader/test_empty', (None, {})),
    ('yandextank/plugins/DataUploader/tests/test_postloader/test_full',
     ('uploader',
      {'api_address': 'https://lunapark.yandex-team.ru/',
       'api_attempts': 2,
       'api_timeout': 5,
       'enabled': True,
       'job_dsc': 'hell of a kitty',
       'job_name': 'Hello kitty',
       'jobno_file': 'jobno.txt',
       'lock_targets': 'foo.bar',
       'maintenance_timeout': 5,
       'network_attempts': 2,
       'operator': 'fomars',
       'package': 'yandextank.plugins.DataUploader',
       'task': 'LOAD-204'})
     ),
    ('yandextank/plugins/DataUploader/tests/test_postloader/test_disabled',
     ('uploader', {'enabled': False, 'package': 'yandextank.plugins.DataUploader'})),
])
def test_from_tank_config(test_dir, expected):
    get_logger()
    assert from_tank_config(test_dir) == expected
