from yandextank.plugins.ConsoleScreen import Screen, CurrentHTTPBlock, CurrentNetBlock
from ConsoleOnlinePluginTest import FakeConsoleMarkup
from TankTests import TankTestCase

class BlocksTestCase(TankTestCase):
    def test_HTTP(self):
        screen = Screen(50, FakeConsoleMarkup())
        block = CurrentHTTPBlock(screen)
        block.render()
        print block.lines
        self.assertEquals('<w>HTTP for 0 RPS:  <rst>', block.lines[0].strip())
        self.assertEquals(1, len(block.lines))
    
        data = self.get_aggregate_data('data/preproc_single.txt')
        data.overall.planned_requests = 100
        data.overall.http_codes = {'400': 10}
        block.add_second(data)
        block.render()
        print block.lines
        self.assertEquals(2, len(block.lines))

        data.overall.http_codes = {'200': 4}
        block.add_second(data)
        block.render()
        print block.lines
        self.assertEquals(3, len(block.lines))

    def test_Net(self):
        screen = Screen(50, FakeConsoleMarkup())
        block = CurrentNetBlock(screen)
        block.render()
        print block.lines
        self.assertEquals('<w> NET for 0 RPS:  <rst>', block.lines[0].strip())
        self.assertEquals(1, len(block.lines))
    
        data = self.get_aggregate_data('data/preproc_single.txt')
        data.overall.planned_requests = 100
        data.overall.net_codes = {'0': 10}
        block.add_second(data)
        block.render()
        print block.lines
        self.assertEquals(2, len(block.lines))

        data.overall.net_codes = {'71': 4}
        block.add_second(data)
        block.render()
        print block.lines
        self.assertEquals(3, len(block.lines))
