import pytest
from mock import MagicMock
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from yandextank.plugins.Pandora import Plugin
# https://raw.githubusercontent.com/yandex/yandex-tank/develop/README.md


class RequestHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.handlers = {
            '/ammo': self._ammo,
        }
        BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

    def _ammo(self):
        return 'application/json', '{"test": "ammo"}'

    def _do_handle(self):
        reply = self.handlers[self.path]()
        self.send_response(200)
        self.send_header('Content-Type', reply[0])
        self.send_header('Content-Length', len(reply[1]))
        self.end_headers()
        self.wfile.write(reply[1])

    def do_GET(self):
        self._do_handle()

    def do_HEAD(self):
        self._do_handle()

    def log_message(self, format, *args):
        pass


class StatHTTPServer(HTTPServer):

    def __init__(self, *args, **kwargs):
        HTTPServer.__init__(self, *args, **kwargs)


SERVER = StatHTTPServer(('localhost', 1234), RequestHandler)
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


def teardown_module(module):
    SERVER.shutdown()
    SERVER.socket.close()
    THREAD.join()
