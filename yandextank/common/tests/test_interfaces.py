import pytest

from yandextank.common.interfaces import TankInfo


class TestStatus(object):

    @pytest.mark.parametrize('updates, result', [
        ([(['plugin', 'key1'], 'foo'), (['plugin', 'key2'], 42)], {'plugin': {'key1': 'foo', 'key2': 42}}),
        ([(['plugin1', 'key1'], 'foo'),
          (['plugin1', 'key2'], 42),
          (['plugin2', 'key1'], 'bar')], {'plugin1': {'key1': 'foo', 'key2': 42},
                                          'plugin2': {'key1': 'bar'}})
    ])
    def test_update(self, updates, result):
        info = TankInfo(dict())
        for args in updates:
            info.update(*args)
        assert info.get_info_dict() == result
