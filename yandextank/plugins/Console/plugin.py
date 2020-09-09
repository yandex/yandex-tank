''' Plugin provides fullscreen console '''
import logging
import sys
import threading
import traceback

from .screen import Screen
from ...common.interfaces import AbstractPlugin, AggregateResultListener


class Plugin(AbstractPlugin, AggregateResultListener):
    ''' Console plugin '''
    SECTION = 'console'

    def __init__(self, core, cfg, name):
        AbstractPlugin.__init__(self, core, cfg, name)
        self.log = logging.getLogger(__name__)
        self.screen = None
        self.render_exception = None
        self.console_markup = None
        self.info_panel_width = self.get_option("info_panel_width")
        self.short_only = self.get_option("short_only")
        # these three provide non-blocking console output
        self.__console_view = None
        self.__writer_thread = None
        self.__writer_event = None
        self.cases_sort_by = self.get_option("cases_sort_by")
        self.cases_max_spark = self.get_option("cases_max_spark")
        self.max_case_len = self.get_option("max_case_len")
        self.times_max_spark = self.get_option("times_max_spark")
        self.sizes_max_spark = self.get_option("sizes_max_spark")

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        return [
            "info_panel_width", "short_only", "disable_all_colors",
            "disable_colors"
        ]

    def configure(self):
        if not self.get_option("disable_all_colors"):
            self.console_markup = RealConsoleMarkup()
        else:
            self.console_markup = NoConsoleMarkup()
        for color in self.get_option("disable_colors").split(' '):
            self.console_markup.__dict__[color] = ''
        self.screen = Screen(
            self.info_panel_width, self.console_markup,
            cases_sort_by=self.cases_sort_by,
            cases_max_spark=self.cases_max_spark,
            max_case_len=self.max_case_len,
            times_max_spark=self.times_max_spark,
            sizes_max_spark=self.sizes_max_spark
        )
        try:
            aggregator = self.core.job.aggregator
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
                    sys.stdout.write(self.__console_view.decode('utf8'))
                    sys.stdout.write(self.console_markup.TOTAL_RESET)

    def is_test_finished(self):
        if not self.__writer_thread:
            self.__writer_event = threading.Event()
            self.__writer_thread = threading.Thread(
                target=self.__console_writer)
            self.__writer_thread.daemon = True
            self.__writer_thread.start()

        try:
            self.__console_view = self.screen.render_screen().encode('utf-8')
        except Exception as ex:
            self.log.warn("Exception inside render: %s", traceback.format_exc())
            self.render_exception = ex
            self.__console_view = ""

        self.__writer_event.set()
        return -1

    def on_aggregated_data(self, data, stats):
        # TODO: use stats data somehow
        if self.short_only:
            overall = data.get('overall')

            quantiles = dict(
                zip(
                    overall['interval_real']['q']['q'],
                    overall['interval_real']['q']['value']))
            info = (
                "ts:{ts}\tRPS:{rps}\tavg:{avg_rt:.2f}\t"
                "min:{min:.2f}\tmax:{q100:.2f}\tq95:{q95:.2f}\t").format(
                    ts=data.get('ts'),
                    rps=overall['interval_real']['len'],
                    avg_rt=float(overall['interval_real']['total'])
                    / overall['interval_real']['len'] / 1000.0,
                    min=overall['interval_real']['min'] / 1000.0,
                    q100=quantiles[100] / 1000,
                    q95=quantiles[95] / 1000)
            self.log.info(info)
        else:
            self.screen.add_second_data(data)

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
    new_line = "\n"

    YELLOW = '\033[1;33m'
    RED = '\033[1;31m'
    RED_DARK = '\033[31;3m'
    RESET = WHITE_ON_BLACK + '\033[1;m'
    CYAN = "\033[1;36m"
    GREEN = "\033[1;32m"
    WHITE = "\033[1;37m"
    MAGENTA = '\033[1;35m'
    BG_MAGENTA = '\033[1;45m'
    BG_GREEN = '\033[1;42m'
    BG_BROWN = '\033[1;43m'
    BG_CYAN = '\033[1;46m'

    def get_markup_vars(self):
        return [
            self.YELLOW, self.RED, self.RESET, self.CYAN, self.BG_MAGENTA,
            self.WHITE, self.BG_GREEN, self.GREEN, self.BG_BROWN,
            self.RED_DARK, self.MAGENTA, self.BG_CYAN
        ]

    def clean_markup(self, orig_str):
        ''' clean markup from string '''
        for val in self.get_markup_vars():
            orig_str = orig_str.replace(val, '')
        return orig_str


# ======================================================
# FIXME: 3 better way to have it?


class NoConsoleMarkup(RealConsoleMarkup):
    ''' all colors are disabled '''
    WHITE_ON_BLACK = ''
    TOTAL_RESET = ''
    clear = ""
    new_line = "\n"

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
