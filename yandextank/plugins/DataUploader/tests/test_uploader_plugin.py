import pytest


from yandextank.plugins.DataUploader.plugin import BackendTypes


class TestBackendTypes(object):

    @pytest.mark.parametrize('section_name, expected_type', [
        ('meta', BackendTypes.LUNAPARK),
        ('meta-01', BackendTypes.LUNAPARK),
        ('lp', BackendTypes.LUNAPARK),
        ('lp-01', BackendTypes.LUNAPARK),
        ('lunapark', BackendTypes.LUNAPARK),
        ('lunapark-1', BackendTypes.LUNAPARK),
        ('overload', BackendTypes.OVERLOAD),
        ('overload-01', BackendTypes.OVERLOAD)
    ])
    def test_identify(self, section_name, expected_type):
        assert BackendTypes.identify_backend(section_name) == expected_type

    @pytest.mark.parametrize('section_name', [
        'meta lunapark',
        'meta ',
        ' lunapark',
        'lp ',
        'meta-'
    ])
    def test_exception(self, section_name):
        with pytest.raises(KeyError) as excinfo:
            BackendTypes.identify_backend(section_name)
        assert 'section name' in str(excinfo.value)
