import pytest

from yandextank.stepper.missile import _parse_header
from yandextank.stepper.module_exceptions import AmmoFileError


class TestParseHeader(object):
    def test_parses_header_with_colon(self):
        assert _parse_header(b'Content-Type: application/json') == {
            'Content-Type': 'application/json'
        }

    def test_strips_whitespace(self):
        assert _parse_header(b'  X-Custom :  value  ') == {'X-Custom': 'value'}

    def test_allows_empty_value(self):
        assert _parse_header(b'X-Empty:') == {'X-Empty': ''}

    def test_splits_on_first_colon_only(self):
        assert _parse_header(b'X: a: b: c') == {'X': 'a: b: c'}

    def test_missing_colon_raises_clear_error(self):
        with pytest.raises(AmmoFileError, match="Malformed header line"):
            _parse_header(b'NoColonHere')

    def test_empty_header_raises_clear_error(self):
        with pytest.raises(AmmoFileError, match="Malformed header line"):
            _parse_header(b'')
