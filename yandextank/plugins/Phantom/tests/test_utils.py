from unittest import mock

from yandextank.plugins.Phantom.utils import PhantomConfig


class TestPhantomConfig(object):
    def test_config_file_uses_predefined_config(self):
        core = mock.Mock()
        stat_log = '/tmp/phantom_stat.log'
        cfg = {
            'config': '/tmp/ready-phantom.conf',
        }

        phantom = PhantomConfig(core, cfg, stat_log)

        # A predefined config must be used as-is, without generation.
        assert phantom.config_file == '/tmp/ready-phantom.conf'
        core.mkstemp.assert_not_called()

    def test_config_file_generates_when_no_predefined_config(self):
        core = mock.Mock()
        core.mkstemp.return_value = '/tmp/generated-phantom.conf'
        stat_log = '/tmp/phantom_stat.log'
        cfg = {}

        phantom = PhantomConfig(core, cfg, stat_log)
        phantom.streams = []
        phantom.threads = '1'
        phantom.phantom_log = '/tmp/phantom.log'
        phantom.stat_log = stat_log
        phantom.additional_libs = ''
        phantom.phantom_modules_path = None

        assert phantom.config_file == '/tmp/generated-phantom.conf'
        core.mkstemp.assert_called_once()
