import unittest.mock as mock

import pytest

from yandextank.stepper.missile import (
    AccessLogReader,
    AmmoFileReader,
    UriPostReader,
    UriReader,
)


@pytest.mark.parametrize('reader_cls', [AmmoFileReader, AccessLogReader, UriReader, UriPostReader])
def test_reader_uses_passed_resource_manager(reader_cls):
    # ulta passes its own manager (adds the OAuth scheme to proxy.sandbox tokens); the global fallback does not
    rm = mock.Mock()
    assert reader_cls('https://proxy.sandbox.yandex-team.ru/1', resource_manager=rm).resource_manager is rm
