import pytest

from yandextank.config_converter.converter import Section


class TestSection(object):
    @pytest.mark.parametrize('options, expected', [
        (
            [
                ('connection_timeout', '10'),
                ('ignore_target_lock', '1'),
                ('some_stupid_comment', 'Here I go!'),
                ('another_stupid_comment', 'I\'m here!'),
            ],
            {
                'ignore_target_lock': True,
                'connection_timeout': 10,
                'meta': {
                    'some_stupid_comment': 'Here I go!',
                    'another_stupid_comment': 'I\'m here!'
                }
            }
        )
    ])
    def test_merged_options(self, options, expected):
        assert Section('meta', 'DataUploader', options).merged_options == expected
