import threading
import os

from yandextank.core.tankcore import TankCore
from yandextank.plugins.Telegraf import Plugin as TelegrafPlugin
try:
    from yatest import common
    PATH = common.source_path('load/projects/yandex-tank/yandextank/plugins/Telegraf/tests')
except ImportError:
    PATH = os.path.dirname(__file__)


class TestTelegrafPlugin(object):
    def test_plugin_configuration(self):
        """ testing telegraf plugin configuration """
        cfg = {
            'core': {},
            'telegraf': {
                'package': 'yandextank.plugins.Telegraf',
                'enabled': True,
                'config': os.path.join(PATH, 'telegraf_mon.xml')
            }
        }
        core = TankCore(cfg, threading.Event())
        telegraf_plugin = core.get_plugin_of_type(TelegrafPlugin)
        telegraf_plugin.configure()
        assert telegraf_plugin.detected_conf == 'telegraf'

    def test_legacy_plugin_configuration(self):
        """ testing legacy plugin configuration, old-style monitoring """
        cfg = {
            'core': {},
            'monitoring': {
                'package': 'yandextank.plugins.Telegraf',
                'enabled': True,
                'config': os.path.join(PATH, 'old_mon.xml')
            }
        }
        core = TankCore(cfg, threading.Event())
        telegraf_plugin = core.get_plugin_of_type(TelegrafPlugin)
        telegraf_plugin.configure()
        assert telegraf_plugin.detected_conf == 'monitoring'
