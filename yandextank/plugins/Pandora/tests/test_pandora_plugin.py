import pytest
from mock import MagicMock

from yandextank.plugins.Pandora import Plugin


@pytest.mark.parametrize('cfg, expected', [
    (
        {'pools': [
            {
                'ammo': {'uri-headers': '[User-Agent: Wget/1.13.4 (linux-gnu)] [Host: foo.ru] [Accept-Encoding: gzip,deflate,sdch]',
                         'type': 'uri',
                         'file': 'https://raw.githubusercontent.com/yandex/yandex-tank/develop/README.md'
                         }
            }]},
        {'pools': [
            {
                'ammo': {'uri-headers': '[User-Agent: Wget/1.13.4 (linux-gnu)] [Host: foo.ru] [Accept-Encoding: gzip,deflate,sdch]',
                         'type': 'uri',
                         'file': 'some local file'}
            }]}
    )
])
def test_patch_config(cfg, expected):
    plugin = Plugin(MagicMock(), {}, 'pandora')
    # '/tmp/9b73d966bcbf27467d4c4190cfe58c2a.downloaded_resource'
    filename = plugin.patch_config(cfg)['pools'][0]['ammo']['file']
    assert filename.endswith('.downloaded_resource')
