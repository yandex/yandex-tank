from contextlib import nullcontext
from http.server import SimpleHTTPRequestHandler, HTTPServer

import pytest
from mock import MagicMock
from threading import Thread

from library.python.port_manager import PortManager
from yandextank.plugins.Pandora import Plugin

# https://raw.githubusercontent.com/yandex/yandex-tank/develop/README.md


# Порт тестового сервера подставляется в конфиги на лету: раньше он был зашит
# константой 1234 и при параллельном прогоне оказывался занят соседним процессом.
AMMO_PORT_PLACEHOLDER = '{ammo_port}'
AMMO_URL = 'http://localhost:{ammo_port}/ammo'


def with_ammo_port(value, port):
    if isinstance(value, dict):
        return {k: with_ammo_port(v, port) for k, v in value.items()}
    if isinstance(value, list):
        return [with_ammo_port(v, port) for v in value]
    if isinstance(value, str):
        return value.replace(AMMO_PORT_PLACEHOLDER, str(port))
    return value


class RequestHandler(SimpleHTTPRequestHandler):

    def _do_handle(self):
        content = '{"test": "ammo"}'.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(content))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        self._do_handle()

    def do_HEAD(self):
        self._do_handle()


@pytest.fixture(scope='module')
def pandora_server():
    with PortManager() as pm:
        port = pm.get_port()
    server = HTTPServer(('localhost', port), RequestHandler)
    t = Thread(target=server.serve_forever, name="StatServer")
    try:
        t.start()
        yield port
    finally:
        server.shutdown()
        server.socket.close()
        t.join()


@pytest.mark.parametrize(
    'cfg, expected',
    [
        (
            {
                'pools': [
                    {
                        'ammo': {
                            'uri-headers': '[User-Agent: Wget/1.13.4 (linux-gnu)] [Host: foo.ru] [Accept-Encoding: gzip,deflate,sdch]',
                            'type': 'uri',
                            'file': AMMO_URL,
                        },
                        'gun': {'answlog': {'enabled': 'true', 'path': 'answ.log', 'filter': 'error'}},
                    }
                ]
            },
            {
                'pools': [
                    {
                        'ammo': {
                            'uri-headers': '[User-Agent: Wget/1.13.4 (linux-gnu)] [Host: foo.ru] [Accept-Encoding: gzip,deflate,sdch]',
                            'type': 'uri',
                            'file': 'some local file',
                        },
                        'gun': {'answlog': {'enabled': 'true', 'path': 'answ.log', 'filter': 'error'}},
                    }
                ]
            },
        )
    ],
)
def test_patch_config(cfg, expected, pandora_server):
    cfg = with_ammo_port(cfg, pandora_server)
    plugin = Plugin(MagicMock(), {}, 'pandora')
    # '/tmp/9b73d966bcbf27467d4c4190cfe58c2a.downloaded_resource'
    filename = plugin.patch_config(cfg)['pools'][0]['ammo']['file']
    assert filename.endswith('.downloaded_resource')


@pytest.mark.parametrize(
    'has_monitoring, monitoring, expected_monitoring, expected_enabled, expected_port',
    [
        (False, None, {'expvar': {'enabled': True, 'port': 1234}}, True, 1234),
        (True, None, {'expvar': {'enabled': True, 'port': 1234}}, True, 1234),
        (True, {}, {'expvar': {'enabled': True, 'port': 1234}}, True, 1234),
        (True, {'expvar': False}, {'expvar': False}, False, 1234),
        (
            True,
            {'cpuprofile': {'enabled': True}},
            {
                'cpuprofile': {'enabled': True},
                'expvar': {'enabled': True, 'port': 1234},
            },
            True,
            1234,
        ),
        (
            True,
            {'expvar': {'enabled': False, 'port': 4321}},
            {'expvar': {'enabled': False, 'port': 4321}},
            False,
            4321,
        ),
        (
            True,
            {'expvar': {'enabled': True, 'port': 4321}},
            {'expvar': {'enabled': True, 'port': 4321}},
            True,
            4321,
        ),
    ],
)
def test_patch_config_normalizes_expvar_monitoring(
    has_monitoring,
    monitoring,
    expected_monitoring,
    expected_enabled,
    expected_port,
):
    config = {
        'pools': [
            {
                'ammo': {},
                'gun': {},
                'result': {'type': 'phout', 'destination': 'phout.log'},
            }
        ]
    }
    if has_monitoring:
        config['monitoring'] = monitoring
    plugin = Plugin(MagicMock(), {}, 'pandora')

    result = plugin.patch_config(config)

    assert result is config
    assert result['monitoring'] == expected_monitoring
    assert plugin.expvar_enabled is expected_enabled
    assert plugin.expvar_port == expected_port


@pytest.mark.parametrize('monitoring', [None, {'cpuprofile': {'enabled': True}}])
def test_patch_config_normalizes_legacy_expvar_mode(monitoring):
    config = {
        'pools': [
            {
                'ammo': {},
                'gun': {},
                'result': {'type': 'phout', 'destination': 'phout.log'},
            }
        ]
    }
    if monitoring is not None:
        config['monitoring'] = monitoring
    plugin = Plugin(MagicMock(), {'expvar': True}, 'pandora')

    result = plugin.patch_config(config)

    assert result['monitoring']['expvar'] == {'enabled': True, 'port': 1234}
    assert plugin.expvar_enabled is True
    assert plugin.expvar_port == 1234


def test_patch_config_resets_expvar_state_between_calls():
    def make_config(monitoring=None):
        config = {
            'pools': [
                {
                    'ammo': {},
                    'gun': {},
                    'result': {'type': 'phout', 'destination': 'phout.log'},
                }
            ]
        }
        if monitoring is not None:
            config['monitoring'] = monitoring
        return config

    plugin = Plugin(MagicMock(), {}, 'pandora')
    plugin.patch_config(make_config({'expvar': {'enabled': True, 'port': 4321}}))

    result = plugin.patch_config(make_config())

    assert result['monitoring']['expvar'] == {'enabled': True, 'port': 1234}
    assert plugin.expvar_enabled is True
    assert plugin.expvar_port == 1234


@pytest.mark.parametrize(
    'pandora_custom_phout, cfg, expected_value, expected_error',
    [
        (  # Test default result type
            None,
            {
                'pools': [
                    {
                        'ammo': {
                            'uri-headers': '[User-Agent: Wget/1.13.4 (linux-gnu)] [Host: foo.ru] [Accept-Encoding: gzip,deflate,sdch]',
                            'type': 'uri',
                            'file': AMMO_URL,
                        },
                        'gun': {'answlog': {'enabled': 'true', 'path': 'answ.log', 'filter': 'error'}},
                        'result': {'type': 'custom', 'custom path': 'result.phout'},
                    }
                ]
            },
            {
                'pools': [
                    {
                        'ammo': {
                            'uri-headers': '[User-Agent: Wget/1.13.4 (linux-gnu)] [Host: foo.ru] [Accept-Encoding: gzip,deflate,sdch]',
                            'type': 'uri',
                            'file': 'some local file',
                        },
                        'gun': {'answlog': {'enabled': 'true', 'path': 'answ.log', 'filter': 'error'}},
                        'result': {'type': 'phout', 'destination': '0_phout.log'},
                    }
                ],
                'monitoring': {'expvar': {'enabled': True, 'port': 1234}},
            },
            nullcontext(),
        ),
        (  # Test custom result type
            'custom path',
            {
                'pools': [
                    {
                        'ammo': {
                            'uri-headers': '[User-Agent: Wget/1.13.4 (linux-gnu)] [Host: foo.ru] [Accept-Encoding: gzip,deflate,sdch]',
                            'type': 'uri',
                            'file': AMMO_URL,
                        },
                        'gun': {'answlog': {'enabled': 'true', 'path': 'answ.log', 'filter': 'error'}},
                        'result': {'type': 'custom', 'custom path': 'result.phout'},
                    }
                ]
            },
            {
                'pools': [
                    {
                        'ammo': {
                            'uri-headers': '[User-Agent: Wget/1.13.4 (linux-gnu)] [Host: foo.ru] [Accept-Encoding: gzip,deflate,sdch]',
                            'type': 'uri',
                            'file': 'some local file',
                        },
                        'gun': {'answlog': {'enabled': 'true', 'path': 'answ.log', 'filter': 'error'}},
                        'result': {'type': 'custom', 'custom path': 'result.phout'},
                    }
                ],
                'monitoring': {'expvar': {'enabled': True, 'port': 1234}},
            },
            nullcontext(),
        ),
        (  # Test improperly set custom result type
            'custom path',
            {
                'pools': [
                    {
                        'ammo': {
                            'uri-headers': '[User-Agent: Wget/1.13.4 (linux-gnu)] [Host: foo.ru] [Accept-Encoding: gzip,deflate,sdch]',
                            'type': 'uri',
                            'file': AMMO_URL,
                        },
                        'gun': {'answlog': {'enabled': 'true', 'path': 'answ.log', 'filter': 'error'}},
                        'result': {},
                    }
                ]
            },
            None,
            pytest.raises(RuntimeError),
        ),
        (  # Test list of pools with improperly set custom path
            'custom path',
            {
                'pools': [
                    {
                        'ammo': {
                            'uri-headers': '[User-Agent: Wget/1.13.4 (linux-gnu)] [Host: foo.ru] [Accept-Encoding: gzip,deflate,sdch]',
                            'type': 'uri',
                            'file': AMMO_URL,
                        },
                        'gun': {'answlog': {'enabled': 'true', 'path': 'answ.log', 'filter': 'error'}},
                        'result': {'type': 'custom', 'custom path': 'result.phout'},
                    },
                    {
                        'ammo': {
                            'uri-headers': '[User-Agent: Wget/1.13.4 (linux-gnu)] [Host: foo.ru] [Accept-Encoding: gzip,deflate,sdch]',
                            'type': 'uri',
                            'file': AMMO_URL,
                        },
                        'gun': {'answlog': {'enabled': 'true', 'path': 'answ.log', 'filter': 'error'}},
                        'result': {'type': 'custom', 'destination': 'result.phout'},
                    },
                ]
            },
            None,
            pytest.raises(RuntimeError),
        ),
    ],
)
def test_patch_config_with_pandora_custom_phout(
    pandora_custom_phout,
    cfg,
    expected_value,
    expected_error,
    pandora_server,
    tmp_path,
):
    cfg = with_ammo_port(cfg, pandora_server)

    # Test that pandora_custom_phout setting working correctly
    core = MagicMock()
    file_opener = MagicMock()
    file_opener.filename = 'some local file'
    core.resource_manager.get_opener.return_value = file_opener

    plugin = Plugin(core, {}, 'pandora')
    plugin.pandora_custom_phout = pandora_custom_phout
    plugin.config_contents = cfg

    with expected_error:
        result = plugin.patch_config(cfg)

    if expected_value is None:
        return

    assert expected_value == result

    # Test that correct filename is added to artifacts
    result_field_name = 'destination' if not plugin.pandora_custom_phout else plugin.pandora_custom_phout
    filename = result['pools'][0]['result'][result_field_name]
    file_ = tmp_path / filename
    file_.write_text('test', encoding='utf-8')
    plugin._add_report_files_to_artifacts()

    core.add_artifact_file.assert_called()
    core.add_artifact_file.assert_called_with(filename)


@pytest.mark.parametrize(
    'line', ['panic: short description', 'today ERROR shit happens', 'again\tFATAL oops i did it again']
)
def test_log_line_contains_error(line):
    assert Plugin.check_log_line_contains_error(line)


@pytest.mark.parametrize(
    'line',
    [
        'not a panic: actually',
        'just string',
    ],
)
def test_log_line_contains_no_error(line):
    assert not Plugin.check_log_line_contains_error(line)
