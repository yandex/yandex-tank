from collections import Counter
import os.path
import threading

import yaml
import pytest

from yandextank.ammo_validator import validate
from yandextank.ammo_validator.common import Message
from yandextank.common.interfaces import TankInfo
from yandextank.common.util import get_test_path
from yandextank.core import TankCore
from yandextank.contrib.netort.netort.resource import ResourceManager, ResourceManagerConfig


@pytest.fixture
def resource_manager() -> ResourceManager:
    rm_cf = ResourceManagerConfig()
    rm_cf.tmp_path = '/tmp'
    return ResourceManager(rm_cf)


def generate_config(generator: str, ammotype: str, ammofile: str) -> TankCore:
    match generator:
        case 'phantom':
            config = {
                'phantom': {
                    'package': 'yandextank.plugins.Phantom',
                    'enabled': True,
                    'address': 'localhost',
                    'load_profile': {'load_type': 'rps', 'schedule': 'line(1, 10, 1m)'},
                    'connection_test': False,
                    'ammo_type': ammotype,
                    'ammofile': ammofile,
                }
            }
            core = TankCore([config], threading.Event(), TankInfo({}))
        case 'pandora':
            config = {
                'pandora': {
                    'package': 'yandextank.plugins.Pandora',
                    'enabled': True,
                    'resources': [],
                    'config_content': {
                        'pools': [
                            {
                                'ammo': {'file': ammofile, 'type': ammotype},
                                'id': 'HTTP pool',
                                'gun': {'type': 'http', 'target': 'localhost', 'ssl': False},
                                'result': {'type': 'phout', 'destination': 'phout.log'},
                                'rps': [{'duration': '2s', 'type': 'step', 'from': 1, 'to': 1000, 'step': 2}],
                                'startup': {'type': 'once', 'times': 100},
                            }
                        ]
                    },
                }
            }
            core = TankCore([config], threading.Event(), TankInfo({}))
            core.plugins_configure()
            core.plugins_prepare_test()
        case _:
            raise ValueError(f'Unknown generator: {generator}')
    return core


def squash_messages(messages: list[Message]) -> dict[str, int]:
    return Counter(m.msg for m in messages)


@pytest.mark.parametrize(
    'ammotype, ammofile, expected_info, expected_warning, expected_error',
    [
        (
            'phantom',
            'test-phantom',
            {'3 packets read (3 successes)': 1},
            {},
            {'Invalid HTTP header - body size is bigger than Content-Length': 1},
        ),
        ('phantom', 'test-phantom-binary', {'1 packets read (1 successes)': 1}, {}, {}),
        ('uri', 'test-uri', {'4 non empty lines read (2 uris)': 1}, {}, {}),
        ('uri', 'test-uri-2', {'2 non empty lines read (2 uris)': 1}, {}, {}),
        (
            'uri',
            'test-uri-bad',
            {'3 non empty lines read (1 uris)': 1},
            {'Too many tags. Only one tag is allowed': 1},
            {'Header line does not end with "]"': 1},
        ),
        ('uripost', 'test-uripost', {'2 packets read (2 successes)': 1}, {}, {}),
        (
            'uripost',
            'test-uripost-bad-1',
            {'1 packets read (0 successes)': 1},
            {},
            {'Invalid size of packet data': 1, 'No successful readed packets in ammo': 1},
        ),
        ('uripost', 'test-uripost-bad-2', {'1 packets read (1 successes)': 1}, {}, {'Packet size not a number': 1}),
        (
            'http/json',
            'test-json-http',
            {'9 non empty lines read. 4 packets seems good': 1},
            {},
            {
                'Error at parse line as JSON': 2,
                '"method" field required': 2,
                '"host" field required': 2,
                '"uri" field required': 1,
            },
        ),
        (
            'grpc/json',
            'test-json-grpc',
            {'6 non empty lines read. 3 packets seems good': 1},
            {},
            {'"call" field required': 2, 'Error at parse line as JSON': 1},
        ),
    ],
)
@pytest.mark.parametrize('generator', ['phantom', 'pandora'])
def test_validate(resource_manager, generator, ammotype, ammofile, expected_info, expected_warning, expected_error):
    if generator == 'phantom' and ammotype in ('http/json', 'grpc/json'):
        pytest.skip('Pandora does not support Phantom ammo')

    if generator == 'pandora' and ammotype == 'phantom':
        ammotype = 'raw'

    core = generate_config(
        generator, ammotype, os.path.join(get_test_path(), f'yandextank/ammo_validator/tests/{ammofile}')
    )

    msgs = validate(resource_manager, core)  # type: ignore
    assert squash_messages(msgs.errors) == expected_error
    assert squash_messages(msgs.warnings) == expected_warning
    assert squash_messages(msgs.infos) == expected_info


def test_pandora_inline(resource_manager):
    with open(os.path.join(get_test_path(), 'yandextank/ammo_validator/tests/test-pandora-inline.yaml')) as f:
        config = yaml.safe_load(f)
    core = TankCore([config], threading.Event(), TankInfo({}))
    core.plugins_configure()
    core.plugins_prepare_test()

    msgs = validate(resource_manager, core)  # type: ignore
    assert squash_messages(msgs.errors) == {}
    assert squash_messages(msgs.warnings) == {}
    assert squash_messages(msgs.infos) == {'1 uris': 1}
