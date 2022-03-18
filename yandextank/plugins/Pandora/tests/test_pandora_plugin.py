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


SERVER = HTTPServer(('localhost', 1234), RequestHandler)
THREAD = Thread(target=SERVER.serve_forever, name="StatServer")


def setup_module(module):
    THREAD.start()


@pytest.mark.parametrize('cfg, expected', [
    (
        {'pools': [
            {
                'ammo': {'uri-headers': '[User-Agent: Wget/1.13.4 (linux-gnu)] [Host: foo.ru] [Accept-Encoding: gzip,deflate,sdch]',
                         'type': 'uri',
                         'file': 'http://localhost:1234/ammo'
                         },
                'gun': {'answlog': {'enabled': 'true',
                                    'path': 'answ.log',
                                    'filter': 'error'
                                    }
                        }
            }]},
        {'pools': [
            {
                'ammo': {'uri-headers': '[User-Agent: Wget/1.13.4 (linux-gnu)] [Host: foo.ru] [Accept-Encoding: gzip,deflate,sdch]',
                         'type': 'uri',
                         'file': 'some local file'},
                'gun': {'answlog': {'enabled': 'false',
                                    'path': 'answ.log',
                                    'filter': 'error'
                                    }
                        }
            }]}
    )
])
def test_patch_config(cfg, expected):
    plugin = Plugin(MagicMock(), {}, 'pandora')
    # '/tmp/9b73d966bcbf27467d4c4190cfe58c2a.downloaded_resource'
    filename = plugin.patch_config(cfg)['pools'][0]['ammo']['file']
    assert filename.endswith('.downloaded_resource')


@pytest.mark.parametrize('line', [
    'panic: short description',
    'today ERROR shit happens',
    'again\tFATAL oops i did it again'
])
def test_log_line_contains_error(line):
    assert Plugin.check_log_line_contains_error(line)


@pytest.mark.parametrize('line', [
    'not a panic: actually',
    'just string',
])
def test_log_line_contains_no_error(line):
    assert not Plugin.check_log_line_contains_error(line)


def teardown_module(module):
    SERVER.shutdown()
    SERVER.socket.close()
    THREAD.join()
