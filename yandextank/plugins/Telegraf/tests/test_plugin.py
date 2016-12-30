from yandextank.core.tankcore import TankCore
from yandextank.plugins.Telegraf import Plugin as TelegrafPlugin


class TestTelegrafPlugin(object):
    def test_plugin_configuration(self):
        """ testing telegraf plugin configuration """
        core = TankCore()
        telegraf_plugin = TelegrafPlugin(core)
        core.set_option(
            'telegraf', 'config',
            'yandextank/plugins/Telegraf/tests/telegraf_mon.xml')
        telegraf_plugin.configure()
        assert telegraf_plugin.detected_conf == 'telegraf'

    def test_legacy_plugin_configuration(self):
        """ testing legacy plugin configuration, old-style monitoring """
        core = TankCore()
        telegraf_plugin = TelegrafPlugin(core)
        core.set_option(
            'monitoring', 'config',
            'yandextank/plugins/Telegraf/tests/old_mon.xml')
        telegraf_plugin.configure()
        assert telegraf_plugin.detected_conf == 'monitoring'

    def test_both_plugin_configuration(self):
        """ both type of plugin configuration should throw a ValueError """
        core = TankCore()
        telegraf_plugin = TelegrafPlugin(core)
        core.set_option(
            'monitoring', 'config',
            'yandextank/plugins/Telegraf/tests/old_mon.xml')
        core.set_option(
            'telegraf', 'config',
            'yandextank/plugins/Telegraf/tests/telegraf_mon.xml')
        try:
            telegraf_plugin.configure()
        except ValueError:
            pass
