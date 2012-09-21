from Tank.Plugins import Codes
import fcntl
import logging
import os
import struct
import termios
import math
import copy
from Tank.Plugins.Aggregator import SecondAggregateDataItem

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


class Screen(object):
    '''
    Console screen renderer class
    '''
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
        first_row = [CurrentTimesBlock(self), VerticalBlock(CurrentHTTPBlock(self), CurrentNetBlock(self))]
        second_row = [TotalQuantilesBlock(self)]
        self.block_rows = [first_row, second_row]

    def get_right_line(self, widget_output):
        right_line = ''
        if widget_output:
            right_line = widget_output.pop(0)
            if len(right_line) > self.right_panel_width:
                right_line_plain = self.markup.clean_markup(right_line)
                if len(right_line_plain) > self.right_panel_width:
                    right_line = right_line[:self.right_panel_width] + self.markup.RESET
        return right_line


    def render_left_panel(self):
        lines = []
        for row in self.block_rows:
            space_left = self.left_panel_width
            # render blocks
            for block in row:
                block.render()
                space_left -= block.width
            
            # merge blocks output into row
            space = ' ' * int(math.floor(float(space_left) / (len(row) + 1)))
            had_lines = True            
            while had_lines:
                had_lines = False
                line = space
                for block in row:
                    if block.lines:
                        block_line = block.lines.pop(0)
                        line += block_line + ' ' * (block.width - len(self.markup.clean_markup(block_line)))
                        had_lines = True
                    else:
                        line += ' ' * block.width
                    line += space
                lines.append(line)
            lines.append("")
        return lines


    def render_screen(self):
        self.term_width, self.term_height = get_terminal_size()
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
                if widget_out:
                    widget_output += [""]

        left_lines = self.render_left_panel()

        output = []        
        for lineNo in range(1, self.term_height):
            line = " "

            if lineNo > 1 and left_lines:
                left_line = left_lines.pop(0)
                if len(left_line) > self.left_panel_width:
                    left_line_plain = self.markup.clean_markup(left_line)
                    if len(left_line_plain) > self.left_panel_width:
                        left_line = left_line[:self.left_panel_width] + self.markup.RESET
                
                left_line += (' ' * (self.left_panel_width - len(self.markup.clean_markup(left_line)))) 
                line += left_line     
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
        for row in self.block_rows:
            for block in row:
                block.add_second(data)        
        

# ======================================================

class AbstractBlock:
    def __init__(self, screen):
        self.log = logging.getLogger(__name__)
        self.lines = []
        self.width = 0
        self.screen = screen

    def add_second(self, data):
        pass

    def render(self):
        raise RuntimeError("Abstract method needs to be overridden")
    
# ======================================================

class VerticalBlock(AbstractBlock):
    '''
    Block to merge two other blocks vertically
    '''
    def __init__(self, top_block, bottom_block):
        self.top = top_block
        self.bottom = bottom_block

    def render(self):
        self.top.render()
        self.bottom.render()
        self.width = max(self.top.width, self.bottom.width)
        
        self.lines = []
        for line in self.top.lines:
            self.lines.append(line + ' ' * (self.width - self.top.width))
        
        if self.top.lines and self.bottom.lines:
            self.lines.append(' ' * self.width)
            
        for line in self.bottom.lines:
            self.lines.append(line + ' ' * (self.width - self.bottom.width))
            
    def add_second(self, data):
        self.top.add_second(data)
        self.bottom.add_second(data)
            
# ======================================================
class CurrentTimesBlock(AbstractBlock):
    def __init__(self, screen):
        AbstractBlock.__init__(self, screen)
        self.current_codes = {}
        self.current_rps = -1
        self.current_duration = 0
        self.current_count = 0
        self.current_max_rt = 0

    def add_second(self, data):
        self.log.debug("Arrived times dist: %s", data.overall.times_dist)
        rps = data.overall.planned_requests
        if not self.current_rps == rps:
            self.current_rps = rps
            self.current_count = 0
            self.current_max_rt = 0
            self.current_codes = {}
            self.current_duration = 0
        for item in data.overall.times_dist:
            self.current_count += item['count']
            self.current_max_rt = max(self.current_max_rt, item['to'])
            if item['from'] in self.current_codes.keys(): 
                self.current_codes[item['from']]['count'] += item['count']
            else:
                self.current_codes[item['from']] = copy.deepcopy(item)
        self.current_duration += 1
        self.log.debug("Current times dist: %s", self.current_codes)
      
    def render(self):
        self.lines = []
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
        self.times_dist = {}
        self.current_rps = -1
        self.total_count = 0


    def process_dist(self, rps, codes_dist):
        self.log.debug("Arrived codes data: %s", codes_dist)
        self.highlight_codes = []
        if not self.current_rps == rps:
            self.current_rps = rps
            self.total_count = 0
            for key in self.times_dist.keys():
                self.times_dist[key] = 0
        
        for code, count in codes_dist.items():
            self.total_count += count
            self.highlight_codes.append(code)
            if code in self.times_dist.keys():
                self.times_dist[code] += count
            else:
                self.times_dist[code] = count
        
        self.log.debug("Current codes dist: %s", self.times_dist)

    def add_second(self, data):
        rps = data.overall.planned_requests
        codes_dist = data.overall.http_codes
        self.process_dist(rps, codes_dist)
      
    def render(self):
        self.lines = [self.TITLE] 
        #self.width = len(self.lines[0])
        for code, count in sorted(self.times_dist.iteritems()):        
            line = self.format_line(code, count)
            self.width = max(self.width, len(self.screen.markup.clean_markup(line)))
            self.lines.append(line)

    def format_line(self, code, count):
        if self.total_count:
            perc = float(count) / self.total_count
        else:
            perc = 1
        # 11083   5.07%: 304 Not Modified         
        count_len = str(len(str(self.total_count)))
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

    def add_second(self, data):
        rps = data.overall.planned_requests
        codes_dist = data.overall.net_codes
        self.process_dist(rps, codes_dist)
    
    def format_line(self, code, count):
        if self.total_count:
            perc = float(count) / self.total_count
        else:
            perc = 1
        # 11083   5.07%: 304 Not Modified         
        count_len = str(len(str(self.total_count)))
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
            
class TotalQuantilesBlock(AbstractBlock):
    
    def __init__(self, screen):
        AbstractBlock.__init__(self, screen)
        self.total_count = 0
        self.current_max_rt = 0
        self.times_dist = {}

    def add_second(self, data):
        self.times_dist = data.cumulative.times_dist
        self.total_count = data.cumulative.total_count
        if data.cumulative.times_dist:
            self.current_max_rt = data.cumulative.times_dist[max(data.cumulative.times_dist.keys())]['to']
      
    def render(self):
        self.lines = []
        quan = 0
        quantiles = copy.copy(SecondAggregateDataItem.QUANTILES)
        for key, item in sorted(self.times_dist.iteritems()):
            if self.total_count: 
                perc = float(item['count']) / self.total_count
            else:
                perc = 1
            quan += perc 

            while quantiles and quan >= quantiles[0]:
                # FIXME break here could resolve problem
                line = self.format_line(quantiles.pop(0), item['to'])
                self.width = max(self.width, len(line))
                self.lines.append(line)
                
        self.lines.reverse()
        self.lines = ['Total percentiles:'] + self.lines
        self.width = max(self.width, len(self.lines[0]))

    def format_line(self, quan, timing):
        timing_len = str(len(str(self.current_max_rt)))
        tpl = '   %3d%% < %' + timing_len + 'd ms'
        data = (100 * quan, timing)
        left_line = tpl % data
        return left_line
