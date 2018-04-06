import pytest
from yandextank.plugins.ShellExec import Plugin


def test_plugin_execute():
    plugin = Plugin(None, {}, None)
    assert plugin.execute('echo foo') == 0


def test_plugin_execute_raises():
    plugin = Plugin(None, {}, None)
    with pytest.raises(RuntimeError) as error:
        plugin.execute('echo "foo')
        assert 'Subprocess returned 2' in error.message
