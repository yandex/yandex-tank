import pytest
import os
from yandextank.plugins.DataUploader.cli import from_tank_config, get_logger
try:
    from yatest import common
    PATH = common.source_path('load/projects/yandex-tank/yandextank/plugins/DataUploader/tests/')
except ImportError:
    PATH = os.path.dirname(__file__)


@pytest.mark.parametrize('test_dir, expected', [
    (os.path.join(PATH, 'test_postloader/test_empty'), (None, {})),
    (os.path.join(PATH, 'test_postloader/test_full'),
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
    (os.path.join(PATH, 'test_postloader/test_disabled'),
     ('uploader', {'enabled': False, 'package': 'yandextank.plugins.DataUploader'})),
])
def test_from_tank_config(test_dir, expected):
    get_logger()
    assert from_tank_config(test_dir) == expected
