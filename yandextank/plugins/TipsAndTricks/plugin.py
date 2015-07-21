'''
Plugin showing tool learning hints in console
'''

from pkg_resources import resource_stream
from yandextank.plugins.ConsoleOnline import \
    ConsoleOnlinePlugin, AbstractInfoWidget
from yandextank.core import AbstractPlugin
import random
import textwrap


class TipsAndTricksPlugin(AbstractPlugin, AbstractInfoWidget):
    '''
    Tips showing plugin
    '''
    SECTION = 'tips'

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        AbstractInfoWidget.__init__(self)
        lines = resource_stream(__name__, "config/tips.txt").readlines()
        line = random.choice(lines)
        self.section = line[:line.index(':')]
        self.tip = line[line.index(':') + 1:].strip()
        self.disable = 0

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        return ["disable"]

    def configure(self):
        self.disable = int(self.get_option('disable', '0'))

    def prepare_test(self):
        if not self.disable:
            try:
                console = self.core.get_plugin_of_type(ConsoleOnlinePlugin)
            except KeyError, ex:
                self.log.debug("Console not found: %s", ex)
                console = None

            if console:
                console.add_info_widget(self)

    def get_index(self):
        return 10000  # really last index

    def render(self, screen):
        line = screen.markup.WHITE + "Tips & Tricks => " + self.section + screen.markup.RESET + ":\n  "
        line += "\n  ".join(textwrap.wrap(self.tip, screen.right_panel_width - 2))
        return line
