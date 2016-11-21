from Queue import Queue

import pytest
from yandextank.common.util import AddressWizard, Drain


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


class TestDrain(object):
    def test_run(self):
        """
        Test drain's run function (in a same thread)
        """
        source = range(5)
        destination = Queue()
        drain = Drain(source, destination)
        drain.run()
        assert destination.qsize() == 5

    def test_interrupt(self):
        """
        Test we can interrupt the drain
        """
        source = range(1000000)
        destination = Queue()
        drain = Drain(source, destination)
        drain.start()
        drain.close()
        assert destination.qsize() < 1000000

    def test_interrupt_and_wait(self):
        """
        Test we can interrupt the drain
        """
        source = range(1000000)
        destination = Queue()
        drain = Drain(source, destination)
        drain.start()
        drain.wait()
        assert destination.qsize() == 1000000