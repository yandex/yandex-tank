from contextlib import nullcontext
from http.server import SimpleHTTPRequestHandler, HTTPServer

import pytest
from mock import MagicMock
from threading import Thread

from yandextank.plugins.Pandora import Plugin

# https://raw.githubusercontent.com/yandex/yandex-tank/develop/README.md


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
    server = HTTPServer(('localhost', 1234), RequestHandler)
    t = Thread(target=server.serve_forever, name="StatServer")
    try:
        t.start()
        yield
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
                            'file': 'http://localhost:1234/ammo',
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
    plugin = Plugin(MagicMock(), {}, 'pandora')
    # '/tmp/9b73d966bcbf27467d4c4190cfe58c2a.downloaded_resource'
    filename = plugin.patch_config(cfg)['pools'][0]['ammo']['file']
    assert filename.endswith('.downloaded_resource')


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
                            'file': 'http://localhost:1234/ammo',
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
                            'file': 'http://localhost:1234/ammo',
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
                            'file': 'http://localhost:1234/ammo',
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
                            'file': 'http://localhost:1234/ammo',
                        },
                        'gun': {'answlog': {'enabled': 'true', 'path': 'answ.log', 'filter': 'error'}},
                        'result': {'type': 'custom', 'custom path': 'result.phout'},
                    },
                    {
                        'ammo': {
                            'uri-headers': '[User-Agent: Wget/1.13.4 (linux-gnu)] [Host: foo.ru] [Accept-Encoding: gzip,deflate,sdch]',
                            'type': 'uri',
                            'file': 'http://localhost:1234/ammo',
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
