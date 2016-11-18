import pytest
from yandextank.common.util import AddressWizard


class TestAddressWizard(object):

    @pytest.mark.parametrize('address_str, do_test, explicit_port, expected', [
        (u'[coverage-api01i.cloud.load.maps.yandex.net]:80',
         False,
         None,
         (True, '2a02:6b8:c01:105::568:0:14', 80, 'coverage-api01i.cloud.load.maps.yandex.net')),
        (u'[coverage-api01i.cloud.load.maps.yandex.net]:80',
         True,
         None,
         (True, '2a02:6b8:c01:105::568:0:14', 80, 'coverage-api01i.cloud.load.maps.yandex.net')),
        (u'[coverage-api01i.cloud.load.maps.yandex.net]:80',
         False,
         80,
         (True, '2a02:6b8:c01:105::568:0:14', 80, 'coverage-api01i.cloud.load.maps.yandex.net')),
        (u'[coverage-api01i.cloud.load.maps.yandex.net]:80',
         True,
         80,
         (True, '2a02:6b8:c01:105::568:0:14', 80, 'coverage-api01i.cloud.load.maps.yandex.net'))
    ])
    def test_resolve(self, address_str, do_test, explicit_port, expected):
        assert AddressWizard().resolve(address_str, do_test, explicit_port) == expected