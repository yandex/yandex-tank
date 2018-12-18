import pytest


from yandextank.plugins.DataUploader.plugin import BackendTypes


class TestBackendTypes(object):

    @pytest.mark.parametrize('api_address, section_name, expected_type', [
        ('lunapark.foo-bar.ru', 'uploader', BackendTypes.LUNAPARK),
        ('lunapark.test.foo-bar.ru', 'overload', BackendTypes.LUNAPARK),
        ('overload.yandex.net', 'uploade', BackendTypes.OVERLOAD),
        ('localhost', 'lunapark', BackendTypes.LUNAPARK)
    ])
    def test_identify(self, api_address, section_name, expected_type):
        assert BackendTypes.identify_backend(api_address, section_name) == expected_type
