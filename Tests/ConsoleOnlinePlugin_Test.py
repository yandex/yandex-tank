import logging
import unittest

from Tank.Plugins.ConsoleOnline import ConsoleOnlinePlugin, AbstractInfoWidget, \
    RealConsoleMarkup
from Tests.TankTests import TankTestCase
from Tank.Plugins.ConsoleScreen import krutilka


class FakeConsoleMarkup(RealConsoleMarkup):
    clear = "\n[clear]\n"
    new_line = "\n"

    YELLOW = '<y>'
    RED = '<r>'
    RED_DARK = '<rd>'
    RESET = '<rst>'
    CYAN = "<c>"
    WHITE = "<w>"
    GREEN = "<g>"
    MAGENTA = '<m>'
    BG_MAGENTA = '<M>'
    BG_GREEN = '<G>'

    WHITE_ON_BLACK = '<W>'
    TOTAL_RESET = '<RST>'
    BG_BROWN = '<BB>'
    BG_CYAN = '<BC>'
    BG_DARKGRAY = '<BG>'


class CheckerTranslator():
    def __init__(self, owner):
        self.owner = owner
        self.size = 0

    def send_console(self, text):
        markup = FakeConsoleMarkup()
        logging.debug("Console!")
        for line in text.split("\n"):
            line = markup.clean_markup(line).split(" . ")[0]

            if not self.size:
                self.size = len(line)

            if line and self.size and self.size != len(line):
                logging.error("%s|%s|", len(line), line)
                #TankTestCase.fail(self.owner)
            else:
                logging.debug("%s|%s|", len(line), line)


class ConsoleOnlinePluginTestCase(TankTestCase):
    def setUp(self):
        core = self.get_core()
        core.load_configs(['config/console.conf'])
        core.load_plugins()
        self.foo = ConsoleOnlinePlugin(core)
        self.foo.console_markup = FakeConsoleMarkup()


    def tearDown(self):
        del self.foo
        self.foo = None


    def test_run(self):
        self.data = self.get_aggregate_data('data/preproc_single2.txt')
        self.foo.remote_translator = CheckerTranslator(self)
        self.foo.set_option('disable_colors', 'WHITE')
        self.foo.configure()
        self.foo.console_markup = FakeConsoleMarkup()
        self.foo.prepare_test()
        self.foo.add_info_widget(TestWidget())
        self.foo.add_info_widget(TestWidget2())

        self.foo.start_test()
        k = krutilka()
        for i in range(1, 10):
            print k.next()
            self.foo.aggregate_second(self.data)
            self.foo.is_test_finished()
        self.foo.end_test(0)
        self.assertFalse(self.foo.render_exception)


class TestWidget(AbstractInfoWidget):
    def render(self, screen):
        return "Widget Data"


class TestWidget2(AbstractInfoWidget):
    def get_index(self):
        return 100

    def render(self, screen):
        return "Widget Data 2"


if __name__ == '__main__':
    unittest.main()

