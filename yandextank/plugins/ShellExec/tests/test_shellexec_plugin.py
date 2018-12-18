import pytest
from mock import MagicMock
from yandextank.plugins.ShellExec import Plugin


def test_plugin_execute():
    plugin = Plugin(MagicMock(), {}, 'shellexec')
    assert plugin.execute('echo foo') == 0


def test_plugin_execute_raises():
    plugin = Plugin(MagicMock(), {}, 'shellexec')
    with pytest.raises(RuntimeError) as error:
        plugin.execute('echo "foo')
        assert 'Subprocess returned 2' in error.message
