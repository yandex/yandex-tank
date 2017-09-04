import pytest


from yandextank.plugins.DataUploader.plugin import BackendTypes


class TestBackendTypes(object):

    @pytest.mark.parametrize('api_address, expected_type', [
        ('lunapark.foo-bar.ru', BackendTypes.LUNAPARK),
        ('lunapark.test.foo-bar.ru', BackendTypes.LUNAPARK),
        ('overload.yandex.net', BackendTypes.OVERLOAD),
    ])
    def test_identify(self, api_address, expected_type):
        assert BackendTypes.identify_backend(api_address) == expected_type
