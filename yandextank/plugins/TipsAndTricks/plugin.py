'''
Plugin showing tool learning hints in console
'''
import random
import textwrap

from pkg_resources import resource_stream
from ...common.interfaces import AbstractInfoWidget, AbstractPlugin

from ..Console import Plugin as ConsolePlugin


class Plugin(AbstractPlugin, AbstractInfoWidget):
    '''
    Tips showing plugin
    '''
    SECTION = 'tips'

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        AbstractInfoWidget.__init__(self)
        self.lines = [
            l.decode('utf-8')
            for l in resource_stream(__name__, "config/tips.txt").readlines()
        ]
        self.disable = 0

        line = random.choice(self.lines)
        self.section, self.tip = [_.strip() for _ in line.split(':', 1)]
        self.probability = 0.0

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
                console = self.core.get_plugin_of_type(ConsolePlugin)
            except KeyError as ex:
                self.log.debug("Console not found: %s", ex)
                console = None

            if console:
                console.add_info_widget(self)

    def get_index(self):
        return 10000  # really last index

    def render(self, screen):
        if random.random() < self.probability:
            self.probability = 0.0
            line = random.choice(self.lines)
            self.section = line[:line.index(':')]
            self.tip = line[line.index(':') + 1:].strip()
        self.probability += 1e-3
        line = screen.markup.WHITE + "Tips & Tricks => " + \
            self.section + screen.markup.RESET + ":\n  "
        line += "\n  ".join(
            textwrap.wrap(self.tip, screen.right_panel_width - 2))
        return line
