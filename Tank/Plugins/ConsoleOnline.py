from Tank.Core import AbstractPlugin
from Tank.Plugins import Codes
from Tank.Plugins.Aggregator import AggregatorPlugin, AggregateResultListener
import fcntl
import logging
import os
import struct
import sys
import termios
import traceback

# TODO: add avg times: parts & by case
    
class RealConsoleMarkup(object):
    clear = "\x1b[2J\x1b[H"
    new_line = "\n"
    
    YELLOW = '\033[1;33m'
    RED = '\033[1;31m'
    RED_DARK = '\033[31;3m'
    RESET = '\033[1;m'
    CYAN = "\033[1;36m"
    GREEN = "\033[1;32m"
    MAGENTA = '\033[1;35m'
    BG_MAGENTA = '\033[1;45m'
    BG_GREEN = '\033[1;42m'
    
    def clean_markup(self, orig_str):
        for val in [self.YELLOW, self.RED, self.RESET, self.CYAN, self.BG_MAGENTA, self.BG_GREEN, self.GREEN, self.RED_DARK, self.MAGENTA]:
            orig_str = orig_str.replace(val, '')
        return orig_str

class ConsoleOnlinePlugin(AbstractPlugin, AggregateResultListener):
    SECTION = 'console'
    
    def __init__(self, core):
        self.log = logging.getLogger(__name__)
        self.core = core
        self.console_markup = RealConsoleMarkup()
        self.screen = None

    @staticmethod
    def get_key():
        return __file__
    
    def configure(self):
        aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        aggregator.add_result_listener(self)
        self.info_panel_width = self.core.get_option(self.SECTION, "info_panel_width", '33')
        self.short_only = int(self.core.get_option(self.SECTION, "short_only", '0'))
        self.screen = Screen(self.info_panel_width, self.console_markup)
    
    def prepare_test(self):
        pass
    
    def start_test(self):
        pass
    
    def end_test(self, rc):
        #if not self.short_only:
        #    sys.stdout.write(self.console_markup.clear)
        return rc

    def execute(self, cmd):
        pass
    
    def aggregate_second(self, second_aggregate_data):
        if self.short_only:
            tpl = "Time: %s\tExpected RPS: %s\tActual RPS: %s\tActive Threads: %s\tAvg RT: %s"
            o = second_aggregate_data.overall # just to see the next line in IDE
            data = (second_aggregate_data.time, o.planned_requests, o.RPS, o.active_threads, o.avg_response_time)
            self.log.info(tpl % data)
        else:
            try:
                self.screen.add_second_data(second_aggregate_data)    
                console_view = self.screen.render_screen()
                self.log.debug("Console view:\n%s", console_view)
                sys.stdout.write(self.console_markup.clear)
                sys.stdout.write(console_view)
            except Exception, ex:
                self.log.warn("Exception inside render: %s", traceback.format_exc(ex))
            # TODO: add a way to send console view to remote API, via listener notification (avoid DataUploader dependency

    def add_info_widget(self, widget):
        if not self.screen:
            self.log.warn("No screen instance to add widget")
        else:
            self.screen.add_info_widget(widget)
        
# ======================================================

class Screen(object):

    RIGHT_PANEL_SEPARATOR = ' . '
    
    def __init__(self, info_panel_width, markup_provider):
        self.log = logging.getLogger(__name__)
        self.info_panel_percent = int(info_panel_width)
        self.info_widgets = {}
        self.markup = markup_provider
        self.term_height = 25
        self.term_width = 80
        self.right_panel_width = 10
        self.left_panel_width = self.term_width - self.right_panel_width - len(self.RIGHT_PANEL_SEPARATOR)
        self.current_times_block = CurrentTimesBlock(self)
        self.current_http_block = CurrentHTTPBlock(self)
        self.current_net_block = CurrentNetBlock(self)

    @staticmethod
    def get_terminal_size(): 
        defaultSize = (25, 80)
        env = os.environ
        def ioctl_gwinsz(fd):
            try:
                cr = struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
            except:
                cr = defaultSize
            return cr
        cr = ioctl_gwinsz(0) or ioctl_gwinsz(1) or ioctl_gwinsz(2)
        if not cr:
            try:
                fd = os.open(os.ctermid(), os.O_RDONLY)
                cr = ioctl_gwinsz(fd)
                os.close(fd)
            except:
                pass
        if not cr:
            try:
                cr = (env['LINES'], env['COLUMNS'])
            except:
                cr = defaultSize
        return int(cr[1]), int(cr[0])    

    def get_right_line(self, widget_output):
        right_line = ''
        if widget_output:
            right_line = widget_output.pop(0)
            if len(right_line) > self.right_panel_width:
                right_line_plain = self.markup.clean_markup(right_line)
                if len(right_line_plain) > self.right_panel_width:
                    right_line = right_line[:self.right_panel_width] + self.markup.RESET
        return right_line


    def get_left_line(self):
        times_line = ''
        if self.current_times_block.lines:
            times_line = self.current_times_block.lines.pop(0)

        codes_line = ''
        if self.current_http_block.lines or self.current_net_block.lines:
            if self.current_net_block.lines:
                codes_line = self.current_net_block.lines.pop(0)
            else:
                codes_line = self.current_http_block.lines.pop(0)
            clean_http = self.markup.clean_markup(codes_line)
            self.log.debug("Clean HTTP: %s / %s / %s", len(codes_line), len(clean_http), self.current_http_block.width)
            codes_line += ' ' * (self.current_http_block.width - len(clean_http))

        left_line = times_line + ' ' * (self.left_panel_width - len(times_line) - max(self.current_http_block.width, self.current_net_block.width)) + codes_line
            
        if len(left_line) > self.left_panel_width:
            left_line_plain = self.markup.clean_markup(left_line)
            if len(left_line_plain) > self.left_panel_width:
                left_line = left_line[:self.left_panel_width] + self.markup.RESET
        
        left_line += (' ' * (self.left_panel_width - len(self.markup.clean_markup(left_line)))) 

        return left_line

    def render_screen(self):
        self.term_width, self.term_height = self.get_terminal_size()
        self.log.debug("Terminal size: %sx%s", self.term_width, self.term_height)
        self.right_panel_width = int((self.term_width - len(self.RIGHT_PANEL_SEPARATOR)) * (float(self.info_panel_percent) / 100)) - 1
        if self.right_panel_width > 0: 
            self.left_panel_width = self.term_width - self.right_panel_width - len(self.RIGHT_PANEL_SEPARATOR) - 2
        else:
            self.right_panel_width = 0
            self.left_panel_width = self.term_width - 1
        self.log.debug("Left/right panels width: %s/%s", self.left_panel_width, self.right_panel_width)

        if self.right_panel_width:
            widget_output = []
            for index, widget in sorted(self.info_widgets.iteritems(), key=lambda(k, v): (v.get_index(), k)): 
                self.log.debug("Rendering info widget #%s: %s", index, widget)
                widget_out = widget.render(self)
                widget_output += widget_out.split("\n")
                widget_output += [""]

        self.current_times_block.render()
        self.current_http_block.render()
        self.current_net_block.render()
        self.current_net_block.lines.append("")

        output = []        
        for lineNo in range(1, self.term_height):
            line = " "

            if lineNo > 1:
                line += self.get_left_line()    
            else:
                line += ' ' * self.left_panel_width

            if self.right_panel_width:
                line += (self.RIGHT_PANEL_SEPARATOR)
                right_line = self.get_right_line(widget_output)
                line += right_line
                 
            output.append(line)
        return self.markup.new_line.join(output) + self.markup.new_line

    
    def add_info_widget(self, widget):
        if widget.get_index() in self.info_widgets.keys():
            self.log.warning("There is existing info widget with index %s: %s, widget %s skipped", widget.get_index(), self.info_widgets[widget.get_index()], widget)
        else:
            self.info_widgets[widget.get_index()] = widget    


    def add_second_data(self, data):
        self.current_times_block.add_second(data.overall.planned_requests, data.overall.times_dist)
        self.current_http_block.add_second(data.overall.planned_requests, data.overall.http_codes)
        self.current_net_block.add_second(data.overall.planned_requests, data.overall.net_codes)
        #self.recalc_total_quantiles() # TODO: get them from aggregator
        
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

class AbstractBlock:
    def __init__(self, screen):
        self.log = logging.getLogger(__name__)
        self.lines = []
        self.width = 0
        self.screen = screen

    def render(self):
        raise RuntimeError("Abstract method needs to be overridden")
    
# ======================================================

class CurrentTimesBlock(AbstractBlock):
    def __init__(self, screen):
        AbstractBlock.__init__(self, screen)
        self.current_codes = {}
        self.current_rps = -1
        self.current_count = 0
        self.current_max_rt = 0

    def render(self):
        self.lines = []
        self.width = 0
        quan = 0
        current_times = sorted(self.current_codes.iteritems())
        while current_times:
            line, quan = self.format_line(current_times, quan)
            self.width = max(self.width, len(line))
            self.lines.append(line)
        self.lines.reverse()
        self.lines = ['Times for current RPS:'] + self.lines
        self.lines.append("")

        count_len = str(len(str(self.current_count)))
        tpl = ' %' + count_len + 'd %6.2f%%: total'
        self.lines.append(tpl % (self.current_count, 100))
        self.width = max(self.width, len(self.lines[0]))

    def add_second(self, rps, times_dist):
        if not self.current_rps == rps:
            self.current_rps = rps
            self.current_count = 0
            self.current_max_rt = 0
            self.current_codes = {}
        for item in times_dist:
            self.current_count += item['count']
            self.current_max_rt = max(self.current_max_rt, item['to'])
            if item['from'] in self.current_codes.keys(): 
                self.current_codes[item['from']]['count'] += item['count']
            else:
                self.current_codes[item['from']] = item
        self.log.debug("Current rps dist: %s", self.current_codes)
      
    def format_line(self, current_times, quan):
        left_line = ''
        if current_times:
            index, item = current_times.pop(0)
            if self.current_count: 
                perc = float(item['count']) / self.current_count
            else:
                perc = 1
            quan += perc 
            # 30691    9.26%: 010  --  025       68.03%  <  025
            count_len = str(len(str(self.current_count)))
            timing_len = str(len(str(self.current_max_rt)))
            tpl = ' %' + count_len + 'd %6.2f%%: %' + timing_len + 'd -- %' + timing_len + 'd  %6.2f%% < %' + count_len + 'd'
            data = (item['count'], perc * 100, item['from'], item['to'], quan * 100, item['to'])
            left_line = tpl % data
        return left_line, quan

    
# ======================================================

class CurrentHTTPBlock(AbstractBlock):

    TITLE = 'HTTP for current RPS:  '
    def __init__(self, screen):
        AbstractBlock.__init__(self, screen)
        self.current_codes = {}
        self.current_rps = -1
        self.current_count = 0

    def add_second(self, rps, codes_dist):
        self.highlight_codes = []
        if not self.current_rps == rps:
            self.current_rps = rps
            self.current_count = 0
            self.current_codes = {}
        for code, count in codes_dist.items():
            self.current_count += count
            self.highlight_codes.append(code)
            if code in self.current_codes.keys(): 
                self.current_codes[code] += count
            else:
                self.current_codes[code] = count
            
        self.log.debug("Current rps dist: %s", self.current_codes)
      
    def render(self):
        self.lines = [self.TITLE] 
        self.width = len(self.lines[0])
        for code, count in sorted(self.current_codes.iteritems()):        
            line = self.format_line(code, count)
            self.width = max(self.width, len(self.screen.markup.clean_markup(line)))
            self.lines.append(line)

    def format_line(self, code, count):
        if self.current_count:
            perc = float(count) / self.current_count
        else:
            perc = 1
        # 11083   5.07%: 304 Not Modified         
        count_len = str(len(str(self.current_count)))
        if int(code) in Codes.HTTP:
            code_desc = Codes.HTTP[int(code)]
        else:
            code_desc = "N/A"
        tpl = ' %' + count_len + 'd %6.2f%%: %s %s'
        data = (count, perc * 100, code, code_desc)
        left_line = tpl % data
        
        if code in self.highlight_codes:
            if code[0] == '2':
                left_line = self.screen.markup.GREEN + left_line + self.screen.markup.RESET
            elif code[0] == '3':
                left_line = self.screen.markup.CYAN + left_line + self.screen.markup.RESET
            elif code[0] == '4':
                left_line = self.screen.markup.YELLOW + left_line + self.screen.markup.RESET
            elif code[0] == '5':
                left_line = self.screen.markup.RED + left_line + self.screen.markup.RESET
            else:
                left_line = self.screen.markup.MAGENTA + left_line + self.screen.markup.RESET
        
        return left_line

    
# ======================================================

class CurrentNetBlock(CurrentHTTPBlock):
    TITLE = ' NET for current RPS:  '
    
    def format_line(self, code, count):
        if self.current_count:
            perc = float(count) / self.current_count
        else:
            perc = 1
        # 11083   5.07%: 304 Not Modified         
        count_len = str(len(str(self.current_count)))
        if int(code) in Codes.NET:
            code_desc = Codes.NET[int(code)]
        else:
            code_desc = "N/A"
        tpl = ' %' + count_len + 'd %6.2f%%: %s %s'
        data = (count, perc * 100, code, code_desc)
        left_line = tpl % data
        
        if code in self.highlight_codes:
            if code == '0':
                left_line = self.screen.markup.GREEN + left_line + self.screen.markup.RESET
            else:
                left_line = self.screen.markup.RED + left_line + self.screen.markup.RESET
        
        return left_line

# ======================================================
    

