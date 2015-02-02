''' Plugin provides fullscreen console '''
import logging
import sys
import traceback
import threading

from Aggregator import AggregatorPlugin, AggregateResultListener
from ConsoleScreen import Screen
from yandextank.core import AbstractPlugin


class ConsoleOnlinePlugin(AbstractPlugin, AggregateResultListener):
    ''' Console plugin '''
    SECTION = 'console'

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.screen = None
        self.render_exception = None
        self.console_markup = None
        self.remote_translator = None
        self.info_panel_width = '33'
        self.short_only = 0
        # these three provide non-blocking console output
        self.__console_view = None
        self.__writer_thread = None
        self.__writer_event = None

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        return ["info_panel_width", "short_only", "disable_all_colors", "disable_colors"]

    def configure(self):
        self.info_panel_width = self.get_option("info_panel_width", self.info_panel_width)
        self.short_only = int(self.get_option("short_only", '0'))
        if not int(self.get_option("disable_all_colors", '0')):
            self.console_markup = RealConsoleMarkup()
        else:
            self.console_markup = NoConsoleMarkup()
        for color in self.get_option("disable_colors", '').split(' '):
            self.console_markup.__dict__[color] = ''
        self.screen = Screen(self.info_panel_width, self.console_markup)

        try:
            aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
            aggregator.add_result_listener(self)
        except KeyError:
            self.log.debug("No aggregator for console")
            self.screen.block_rows = []
            self.screen.info_panel_percent = 100

    def __console_writer(self):
        while True:
          self.__writer_event.wait()
          self.__writer_event.clear()

          if self.__console_view:
              if not self.short_only:
                  self.log.debug("Writing console view to STDOUT")
                  sys.stdout.write(self.console_markup.clear)
                  sys.stdout.write(self.__console_view)
                  sys.stdout.write(self.console_markup.TOTAL_RESET)

              if self.remote_translator:
                  self.remote_translator.send_console(console_view)

    def is_test_finished(self):
        if not self.__writer_thread:
          self.__writer_event = threading.Event()
          self.__writer_thread = threading.Thread(target=self.__console_writer)
          self.__writer_thread.daemon = True
          self.__writer_thread.start()

        try:
            self.__console_view = self.screen.render_screen().encode('utf-8')
        except Exception, ex:
            self.log.warn("Exception inside render: %s", traceback.format_exc(ex))
            self.render_exception = ex
            self.__console_view = ""

        self.__writer_event.set()
        return -1


    def aggregate_second(self, second_aggregate_data):
        self.screen.add_second_data(second_aggregate_data)
        if self.short_only:
            tpl = "Time: %s\tExpected RPS: %s\tActual RPS: %s\tActive Threads: %s\tAvg RT: %s"
            ovr = second_aggregate_data.overall  # just to see the next line in IDE
            data = (second_aggregate_data.time, ovr.planned_requests, ovr.RPS,
                    ovr.active_threads, ovr.avg_response_time)
            self.log.info(tpl % data)


    def add_info_widget(self, widget):
        ''' add right panel widget '''
        if not self.screen:
            self.log.debug("No screen instance to add widget")
        else:
            self.screen.add_info_widget(widget)


# ======================================================


class RealConsoleMarkup(object):
    '''
    Took colors from here: https://www.siafoo.net/snippet/88
    '''
    WHITE_ON_BLACK = '\033[37;40m'
    TOTAL_RESET = '\033[0m'
    clear = "\x1b[2J\x1b[H"
    new_line = u"\n"

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
    BG_BROWN = '\033[1;43m'
    BG_CYAN = '\033[1;46m'

    def clean_markup(self, orig_str):
        ''' clean markup from string '''
        for val in [self.YELLOW, self.RED, self.RESET,
                    self.CYAN, self.BG_MAGENTA, self.WHITE,
                    self.BG_GREEN, self.GREEN, self.BG_BROWN,
                    self.RED_DARK, self.MAGENTA, self.BG_CYAN]:
            orig_str = orig_str.replace(val, '')
        return orig_str


# ======================================================
# FIXME: 3 better way to have it?

class NoConsoleMarkup(RealConsoleMarkup):
    ''' all colors are disabled '''
    WHITE_ON_BLACK = ''
    TOTAL_RESET = ''
    clear = ""
    new_line = u"\n"

    YELLOW = ''
    RED = ''
    RED_DARK = ''
    RESET = ''
    CYAN = ""
    GREEN = ""
    WHITE = ""
    MAGENTA = ''
    BG_MAGENTA = ''
    BG_GREEN = ''
    BG_BROWN = ''
    BG_CYAN = ''


# ======================================================


class AbstractInfoWidget:
    ''' parent class for all right panel widgets '''

    def __init__(self):
        self.log = logging.getLogger(__name__)

    def render(self, screen):
        raise NotImplementedError()

    def get_index(self):
        ''' get vertical priority index '''
        return 0
