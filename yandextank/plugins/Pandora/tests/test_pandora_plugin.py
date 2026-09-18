from contextlib import nullcontext
import fcntl
from http.server import SimpleHTTPRequestHandler, HTTPServer
import os
import time

import pytest
import requests
import yatest.common
from mock import MagicMock, patch
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


@pytest.mark.parametrize(
    'output, expected',
    [
        ('{"managed_expvar_fd":1}\n', True),
        ('{"managed_expvar_fd":2}\n', False),
        ('{"managed_expvar_fd":true}\n', False),
        ('not json', False),
    ],
)
def test_capability_probe_requires_version_one(output, expected):
    plugin = Plugin(MagicMock(), {}, 'pandora')
    plugin.pandora_cmd = '/path/to/pandora'
    probe = MagicMock(returncode=0, stdout=output)
    with patch('yandextank.plugins.Pandora.plugin.subprocess.run', return_value=probe) as run:
        assert plugin._supports_managed_expvar() is expected
    run.assert_called_once_with(['/path/to/pandora', '-capabilities'], capture_output=True, text=True, timeout=2)


def test_capability_probe_failure_falls_back_to_legacy():
    plugin = Plugin(MagicMock(), {}, 'pandora')
    plugin.pandora_cmd = '/path/to/old-pandora'
    with patch('yandextank.plugins.Pandora.plugin.subprocess.run', side_effect=OSError('cannot probe')):
        assert plugin._supports_managed_expvar() is False


@pytest.mark.parametrize(
    'monitoring, expected',
    [
        (None, True),
        ({'cpuprofile': {'enabled': True}}, True),
        ({'expvar': {'enabled': True, 'port': 4321}}, False),
        ({'expvar': {'enabled': False}}, False),
        ({'expvar': False}, False),
    ],
)
def test_explicit_expvar_configuration_keeps_legacy_mode(monitoring, expected):
    plugin = Plugin(MagicMock(), {}, 'pandora')
    config = {'pools': [{'ammo': {}, 'gun': {}, 'result': {'type': 'phout', 'destination': 'phout.log'}}]}
    if monitoring is not None:
        config['monitoring'] = monitoring
    with patch.object(plugin, '_supports_managed_expvar', return_value=True):
        plugin._configure_expvar_mode(config)
    assert plugin.managed_expvar is expected


@pytest.mark.parametrize(
    'announcement',
    [
        b'{"version":1,"expvar":"0.0.0.0:4321"}\n',
        b'{"version":2,"expvar":"127.0.0.1:4321"}\n',
        b'{"version":1,"expvar":"127.0.0.1:0"}\n',
        b'{"version":1,"expvar":"127.0.0.1:4321"}',
    ],
)
def test_invalid_managed_announcement_uses_zero_fallback(announcement, tmp_path):
    plugin = Plugin(MagicMock(), {}, 'pandora')
    plugin.pandora_cmd = 'pandora'
    plugin.pandora_config_file = 'config.yaml'
    plugin.managed_expvar = True
    plugin.expvar_enabled = True
    plugin.affinity = ''
    plugin.process_stderr_file = str(tmp_path / 'pandora.log')
    plugin.core.mkstemp.return_value = plugin.process_stderr_file
    plugin.get_stats_reader()
    process = MagicMock()

    def announce(args, **kwargs):
        import os

        os.write(kwargs['pass_fds'][0], announcement)
        return process

    with patch('yandextank.plugins.Pandora.plugin.subprocess.Popen', side_effect=announce):
        plugin.start_test()

    process.terminate.assert_not_called()
    assert plugin.stats_reader.expvar is False
    assert plugin.stats_reader.port is None
    plugin.process_stderr.close()
    plugin.stats_reader.close()


def test_managed_start_updates_reader_created_before_pandora(tmp_path):
    plugin = Plugin(MagicMock(), {}, 'pandora')
    plugin.pandora_cmd = 'pandora'
    plugin.pandora_config_file = 'config.yaml'
    plugin.managed_expvar = True
    plugin.expvar_enabled = True
    plugin.affinity = ''
    plugin.process_stderr_file = str(tmp_path / 'pandora.log')
    plugin.core.mkstemp.return_value = plugin.process_stderr_file
    reader = plugin.get_stats_reader()
    assert reader.port is None

    def announce(args, **kwargs):
        import os

        assert args[0] == 'pandora'
        assert args[-1] == 'config.yaml'
        assert args[-2] == f'-managed-expvar-fd={kwargs["pass_fds"][0]}'
        os.write(kwargs['pass_fds'][0], b'{"version":1,"expvar":"127.0.0.1:4321"}\n')
        return MagicMock()

    with patch('yandextank.plugins.Pandora.plugin.subprocess.Popen', side_effect=announce):
        plugin.start_test()

    assert plugin.get_stats_reader() is reader
    assert reader.port == 4321
    assert reader.poller.port == 4321
    plugin.process_stderr.close()


def test_legacy_start_keeps_existing_cli_and_port(tmp_path):
    plugin = Plugin(MagicMock(), {'expvar': True}, 'pandora')
    plugin.pandora_cmd = 'old-pandora'
    plugin.pandora_config_file = 'config.yaml'
    plugin.affinity = ''
    plugin.process_stderr_file = str(tmp_path / 'pandora.log')
    plugin.core.mkstemp.return_value = plugin.process_stderr_file
    reader = plugin.get_stats_reader()
    with patch('yandextank.plugins.Pandora.plugin.subprocess.Popen', return_value=MagicMock()) as popen:
        plugin.start_test()
    assert reader.port == 1234
    popen.assert_called_once_with(
        ['old-pandora', '-expvar', 'config.yaml'],
        stderr=plugin.process_stderr,
        stdout=plugin.process_stderr,
        close_fds=True,
    )
    plugin.process_stderr.close()


def test_managed_announcement_timeout_keeps_pipe_until_test_ends(tmp_path):
    plugin = Plugin(MagicMock(), {}, 'pandora')
    plugin.pandora_cmd = 'pandora'
    plugin.pandora_config_file = 'config.yaml'
    plugin.managed_expvar = True
    plugin.expvar_enabled = True
    plugin.affinity = ''
    plugin.core.mkstemp.return_value = str(tmp_path / 'pandora.log')
    process = MagicMock()
    process.poll.return_value = 0
    with patch('yandextank.plugins.Pandora.plugin.subprocess.Popen', return_value=process):
        with patch.object(plugin, '_read_managed_port', side_effect=TimeoutError):
            plugin.start_test()

    assert plugin.stats_reader.expvar is False
    assert plugin.stats_reader.port is None
    fd = plugin._managed_control_fd
    os.fstat(fd)
    plugin.end_test(0)
    with pytest.raises(OSError):
        os.fstat(fd)
    plugin.process_stderr.close()


def test_managed_announcement_accepts_high_file_descriptor():
    read_fd, write_fd = os.pipe()
    high_fd = fcntl.fcntl(read_fd, fcntl.F_DUPFD, 1100)
    os.close(read_fd)
    try:
        os.write(write_fd, b'{"version":1,"expvar":"127.0.0.1:4321"}\n')
        assert Plugin._read_managed_port(high_fd) == 4321
    finally:
        os.close(high_fd)
        os.close(write_fd)


def test_real_pandora_managed_expvar_reports_sent_rps(pandora_server, tmp_path):
    pandora_binary = yatest.common.binary_path('load/projects/pandora/pandora')
    phout = tmp_path / 'phout.log'
    config = {
        'pools': [
            {
                'id': 'local-http',
                'gun': {'type': 'http', 'target': f'127.0.0.1:{pandora_server}', 'answlog': {'enabled': False}},
                'ammo': {'type': 'uri', 'uris': ['/']},
                'result': {'type': 'phout', 'destination': str(phout)},
                'rps-per-instance': False,
                'rps': [{'type': 'const', 'ops': 10, 'duration': '6s'}],
                'startup': [{'type': 'once', 'times': 2}],
            }
        ],
        'log': {'level': 'info'},
    }
    core = MagicMock()
    core.mkstemp.side_effect = lambda ext, prefix: str(tmp_path / (prefix + ext))
    plugin = Plugin(core, {'pandora_cmd': pandora_binary, 'config_content': config}, 'pandora')
    plugin.resources = []
    plugin.affinity = ''
    with patch.object(plugin, 'get_resource', return_value=pandora_binary):
        plugin.prepare_resources()

    assert plugin.managed_expvar is True
    reader = plugin.get_stats_reader()
    assert reader.port is None
    next(reader)  # Aggregator starts this reader before Pandora is launched.
    try:
        plugin.start_test()
        assert reader.port is not None
        response = requests.get(f'http://127.0.0.1:{reader.port}/debug/vars', timeout=1)
        response.raise_for_status()
        assert 'engine_ReqPS' in response.json()
        assert plugin.process.wait(timeout=15) == 0
        time.sleep(0.3)
        assert phout.stat().st_size > 0
        assert any(item['metrics']['reqps'] > 0 for item in reader.poller.get_data())
    finally:
        if plugin.process and plugin.process.poll() is None:
            plugin.process.terminate()
            plugin.process.wait(timeout=5)
        reader.close()
        if plugin.process_stderr:
            plugin.process_stderr.close()
