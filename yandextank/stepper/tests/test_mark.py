from yandextank.stepper.mark import __test_missile, get_marker


class TestEnumAmmo(object):
    """`get_marker(..., enum_ammo=True)` must produce bytes markers for both
    bytes-returning and str-returning underlying markers."""

    def test_uri_marker_enum_ammo(self):
        marker = get_marker('uri', True)
        first = marker(__test_missile.encode('utf8'))
        second = marker(__test_missile.encode('utf8'))
        assert isinstance(first, bytes)
        assert first == b'_example_search_hello_help_us#0'
        assert second == b'_example_search_hello_help_us#1'

    def test_uniq_marker_enum_ammo(self):
        marker = get_marker('uniq', True)
        first = marker(__test_missile.encode('utf8'))
        assert isinstance(first, bytes)
        assert first.endswith(b'#0')

    def test_numeric_marker_enum_ammo(self):
        marker = get_marker('3', True)
        assert marker(__test_missile.encode('utf8')) == b'_example_search_hello#0'
        assert marker(__test_missile.encode('utf8')) == b'_example_search_hello#1'

    def test_zero_marker_enum_ammo(self):
        marker = get_marker('0', True)
        assert marker(__test_missile.encode('utf8')) == b'#0'
