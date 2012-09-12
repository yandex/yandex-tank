from Tank.Plugins.ConsoleOnline import CurrentHTTPBlock, Screen
from Tests.ConsoleOnlinePluginTest import FakeConsoleMarkup
from Tests.TankTests import TankTestCase
import logging
import os

class BlocksTestCase(TankTestCase):
    def test_HTTP(self):
        screen = Screen(50, FakeConsoleMarkup())
        block = CurrentHTTPBlock(screen)
        block.render()
        print block.lines
        self.assertEquals('HTTP for current RPS:', block.lines[0].strip())
        self.assertEquals(1, len(block.lines))
    
        block.add_second(100, {'400': 10})
        block.render()
        print block.lines
        self.assertEquals(2, len(block.lines))

        block.add_second(100, {'200': 4})
        block.render()
        print block.lines
        self.assertEquals(3, len(block.lines))
