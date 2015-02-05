from yandextank.plugins.ConsoleOnline import ConsoleOnlinePlugin, AbstractInfoWidget, \
    RealConsoleMarkup
from TankTests import TankTestCase
import tempfile
import unittest
from yandextank.plugins.ConsoleScreen import krutilka

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
        self.foo.set_option('disable_colors', 'WHITE')
        self.foo.configure()
        self.foo.prepare_test()
        self.foo.add_info_widget(TestWidget())
        self.foo.add_info_widget(TestWidget2())
        
        self.foo.start_test()
        k=krutilka()
        for i in range(1, 10):
            print k.next()
            self.foo.aggregate_second(self.data)
        self.foo.end_test(0)
        self.assertFalse(self.foo.render_exception)
        
class TestWidget(AbstractInfoWidget):
    def render(self, screen):
        return "Widget Data";

class TestWidget2(AbstractInfoWidget):
    def get_index(self):
        return 100;
    
    def render(self, screen):
        return "Widget Data 2";


if __name__ == '__main__':
    unittest.main()

