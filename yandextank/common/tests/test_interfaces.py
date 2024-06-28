import pytest
import re
from yandextank.common.interfaces import TankInfo, AbstractCriterion


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


@pytest.mark.parametrize('codes_mask, codes_dict, expected_matched_cnt',
                         [
                             ('', {'200': 500}, 0),  # mask is empty
                             ('1', {'110': 500}, 0),  # mask is prefix
                             ('1', {'21': 500}, 0),  # mask is suffix
                             ('0.', {'0': 500}, 0),  # mask is too long
                             ('2.', {'200': 500}, 0),  # mask is too short
                             ('2..', {'200': 500}, 500),
                             ('2..', {'200': 500, '201': 100}, 600),
                             ('..9', {'999': 500}, 500),
                         ])
def test_match(codes_mask, codes_dict, expected_matched_cnt):
    assert AbstractCriterion.count_matched_codes(codes_regex=re.compile(codes_mask),
                                                 codes_dict=codes_dict) == expected_matched_cnt
