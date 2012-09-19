from Tank.Core import AbstractPlugin
from Tank.Plugins.Aggregator import AggregatorPlugin, AggregateResultListener
from Tank.Plugins.ConsoleScreen import Screen
import traceback
import sys
import logging

# TODO: 1 add avg times: parts & by case    
class RealConsoleMarkup(object):
    '''    
    Took colors from here: https://www.siafoo.net/snippet/88
    '''
    clear = "\x1b[2J\x1b[H"
    new_line = "\n"
    
    YELLOW = '\033[1;33m'
    RED = '\033[1;31m'
    RED_DARK = '\033[31;3m'
    RESET = '\033[1;m'
    CYAN = "\033[1;36m"
    GREEN = "\033[1;32m"
    WHITE = "\033[1;37m"
    MAGENTA = '\033[1;35m'
    BG_MAGENTA = '\033[1;45m'
    BG_GREEN = '\033[1;42m'
    
    def clean_markup(self, orig_str):
        for val in [self.YELLOW, self.RED, self.RESET,
                    self.CYAN, self.BG_MAGENTA, self.WHITE,
                    self.BG_GREEN, self.GREEN,
                    self.RED_DARK, self.MAGENTA]:
            orig_str = orig_str.replace(val, '')
        return orig_str

# ======================================================

class AbstractInfoWidget:
    def __init__(self):
        self.log = logging.getLogger(__name__)

    def render(self, screen):
        self.log.warn("Please, override render widget")
        return "[Please, override render widget]"

    def get_index(self):
        return 0;

# ======================================================

class ConsoleOnlinePlugin(AbstractPlugin, AggregateResultListener):
    SECTION = 'console'
    
    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.console_markup = RealConsoleMarkup()
        self.screen = None
        self.render_exception = None

    @staticmethod
    def get_key():
        return __file__
    
    def configure(self):
        aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        aggregator.add_result_listener(self)
        self.info_panel_width = self.get_option("info_panel_width", '33')
        self.short_only = int(self.get_option("short_only", '0'))
        self.screen = Screen(self.info_panel_width, self.console_markup)
    
    def prepare_test(self):
        pass
    
    def start_test(self):
        pass
    
    def end_test(self, retcode):
        #if not self.short_only:
        #    sys.stdout.write(self.console_markup.clear)
        return retcode

    def execute(self, cmd):
        pass
    
    def aggregate_second(self, second_aggregate_data):
        if self.short_only:
            tpl = "Time: %s\tExpected RPS: %s\tActual RPS: %s\tActive Threads: %s\tAvg RT: %s"
            o = second_aggregate_data.overall # just to see the next line in IDE
            data = (second_aggregate_data.time, o.planned_requests, o.RPS,
                    o.active_threads, o.avg_response_time)
            self.log.info(tpl % data)
        else:
            try:
                self.screen.add_second_data(second_aggregate_data)    
                console_view = self.screen.render_screen()
                sys.stdout.write(self.console_markup.clear)
                sys.stdout.write(console_view.encode('utf-8'))
            except Exception, ex:
                self.log.warn("Exception inside render: %s", traceback.format_exc(ex))
                self.render_exception = ex
            # TODO: 3 add a way to send console view to remote API, via listener notification (avoid DataUploader dependency

    def add_info_widget(self, widget):
        if not self.screen:
            self.log.warn("No screen instance to add widget")
        else:
            self.screen.add_info_widget(widget)
        
