import os
import pytest
import yaml
from yandextank.contrib.netort.netort.data_manager.common.util import expandvars, YamlEnvSubstConfigLoader
from unittest.mock import patch


@pytest.mark.parametrize(
    'in_, default, expected',
    [
        ('STR_${ENV}', None, 'STR_${ENV}'),
        ('STR_${ENV}', '', 'STR_'),
        ('STR_${ENV3}_${ENV2}', 'aa', 'STR_aa_env2_value'),
        ('STR_${SOME_OTHER}_$ENV2', '', 'STR_some other value_$ENV2'),
    ],
)
def test_expandvars(in_, default, expected):
    with patch.dict(os.environ, ENV1='env1_value', ENV2='env2_value', SOME_OTHER='some other value'):
        assert expandvars(in_, default) == expected


def test_YamlEnvSubstConfigLoader():
    config = '''
key:
  subkey: ${ENV1}
  subkey2: token ${ENV2}
  subkey3: not replace
key_reuse: token ${ENV1}
'''
    with patch.dict(os.environ, ENV1='env1_value', ENV2='env2_value'):
        d: dict = yaml.load(config, Loader=YamlEnvSubstConfigLoader)
        assert d['key']['subkey'] == 'env1_value'
        assert d['key']['subkey2'] == 'token env2_value'
        assert d['key']['subkey3'] == 'not replace'
        assert d['key_reuse'] == 'token env1_value'
