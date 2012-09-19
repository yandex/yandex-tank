from Tank.Core import AbstractPlugin
from Tank.Plugins.ConsoleOnline import ConsoleOnlinePlugin, AbstractInfoWidget
import os
import random
import textwrap

class TipsAndTricksPlugin(AbstractPlugin, AbstractInfoWidget):
    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        lines = open(os.path.dirname(__file__) + '/tips.txt').readlines()
        self.tip = random.choice(lines)
        
    @staticmethod
    def get_key():
        return __file__;
    
    def configure(self):
        pass
    
    def prepare_test(self):
        try:
            console = self.core.get_plugin_of_type(ConsoleOnlinePlugin)
        except Exception, ex:
            self.log.debug("Console not found: %s", ex)
            console = None
            
        if console:    
            console.add_info_widget(self)        
    
    def start_test(self):
        pass
        
    def end_test(self, retcode):
        self.log.debug("End2")
        
    def get_index(self):
        return 10000 # really last index    
        

    def render(self, screen):
        line=screen.markup.WHITE+"Tips & Tricks"+screen.markup.RESET+":\n  "
        line+="\n  ".join(textwrap.wrap(self.tip, screen.right_panel_width))
        return line
        
