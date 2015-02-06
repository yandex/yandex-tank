''' Classes to build full console screen '''
import copy
import fcntl
import logging
import math
import os
import struct
import termios

import Codes


def get_terminal_size():
    '''
    Gets width and height of terminal viewport
    '''
    default_size = (60, 140)
    env = os.environ

    def ioctl_gwinsz(file_d):
        '''
        Helper to get console size
        '''
        try:
            sizes = struct.unpack('hh', fcntl.ioctl(file_d, termios.TIOCGWINSZ, '1234'))
        except Exception:
            sizes = default_size
        return sizes

    sizes = ioctl_gwinsz(0) or ioctl_gwinsz(1) or ioctl_gwinsz(2)
    if not sizes:
        try:
            file_d = os.open(os.ctermid(), os.O_RDONLY)
            sizes = ioctl_gwinsz(file_d)
            os.close(file_d.fileno())
        except Exception:
            pass
    if not sizes:
        try:
            sizes = (env['LINES'], env['COLUMNS'])
        except Exception:
            sizes = default_size
    return int(sizes[1]), int(sizes[0])


def krutilka():
    pos = 0
    chars = "|/-\\"
    while True:
        yield chars[pos]
        pos += 1
        if pos >= len(chars):
            pos = 0


class Screen(object):
    '''     Console screen renderer class    '''
    RIGHT_PANEL_SEPARATOR = ' . '

    def __init__(self, info_panel_width, markup_provider):
        self.log = logging.getLogger(__name__)
        self.info_panel_percent = int(info_panel_width)
        self.info_widgets = {}
        self.markup = markup_provider
        self.term_height = 60
        self.term_width = 120
        self.right_panel_width = 10
        self.left_panel_width = self.term_width - self.right_panel_width - len(self.RIGHT_PANEL_SEPARATOR)

        block1 = VerticalBlock(CurrentHTTPBlock(self), CurrentNetBlock(self))
        block2 = VerticalBlock(block1, CasesBlock(self))
        block3 = VerticalBlock(block2, TotalQuantilesBlock(self))
        block4 = VerticalBlock(block3, AnswSizesBlock(self))
        block5 = VerticalBlock(block4, AvgTimesBlock(self))

        self.block_rows = [[CurrentTimesDistBlock(self), block5]]

    def __get_right_line(self, widget_output):
        '''        Gets next line for right panel        '''
        right_line = ''
        if widget_output:
            right_line = widget_output.pop(0)
            if len(right_line) > self.right_panel_width:
                right_line_plain = self.markup.clean_markup(right_line)
                if len(right_line_plain) > self.right_panel_width:
                    right_line = right_line[:self.right_panel_width] + self.markup.RESET
        return right_line


    def __render_left_panel(self):
        ''' Render left blocks '''
        self.log.debug("Rendering left blocks")
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
                #lines.append(".  " * (1 + self.left_panel_width / 3))
                #lines.append("")
        return lines


    def render_screen(self):
        '''        Main method to render screen view        '''
        self.term_width, self.term_height = get_terminal_size()
        self.log.debug("Terminal size: %sx%s", self.term_width, self.term_height)
        self.right_panel_width = int(
            (self.term_width - len(self.RIGHT_PANEL_SEPARATOR)) * (float(self.info_panel_percent) / 100)) - 1
        if self.right_panel_width > 0:
            self.left_panel_width = self.term_width - self.right_panel_width - len(self.RIGHT_PANEL_SEPARATOR) - 2
        else:
            self.right_panel_width = 0
            self.left_panel_width = self.term_width - 1
        self.log.debug("Left/right panels width: %s/%s", self.left_panel_width, self.right_panel_width)

        widget_output = []
        if self.right_panel_width:
            widget_output = []
            for index, widget in sorted(self.info_widgets.iteritems(), key=lambda (k, v): (v.get_index(), k)):
                self.log.debug("Rendering info widget #%s: %s", index, widget)
                widget_out = widget.render(self).strip()
                if widget_out:
                    widget_output += widget_out.split("\n")
                    widget_output += [""]

        left_lines = self.__render_left_panel()

        self.log.debug("Composing final screen output")
        output = []
        for line_no in range(1, self.term_height):
            line = " "

            if line_no > 1 and left_lines:
                left_line = left_lines.pop(0)
                left_line_plain = self.markup.clean_markup(left_line)
                if len(left_line) > self.left_panel_width:
                    if len(left_line_plain) > self.left_panel_width:
                        left_line = left_line[:self.left_panel_width] + self.markup.RESET

                left_line += (' ' * (self.left_panel_width - len(left_line_plain)))
                line += left_line
            else:
                line += ' ' * self.left_panel_width
            if self.right_panel_width:
                line += self.RIGHT_PANEL_SEPARATOR
                right_line = self.__get_right_line(widget_output)
                line += right_line

            output.append(line)
        return self.markup.new_line.join(output) + self.markup.new_line


    def add_info_widget(self, widget):
        '''
        Add widget string to right panel of the screen
        '''
        index = widget.get_index()
        while index in self.info_widgets.keys():
            index += 1
        self.info_widgets[widget.get_index()] = widget


    def add_second_data(self, data):
        '''
        Notification method about new aggregator data
        '''
        for row in self.block_rows:
            for block in row:
                block.add_second(data)


                # ======================================================


class AbstractBlock:
    '''
    Parent class for all left panel blocks
    '''

    def __init__(self, screen):
        self.log = logging.getLogger(__name__)
        self.lines = []
        self.width = 0
        self.screen = screen

    def add_second(self, data):
        '''
        Notification about new aggregate data
        '''
        pass

    def render(self):
        '''
        Render method, fills .lines and .width properties with rendered data
        '''
        raise RuntimeError("Abstract method needs to be overridden")


# ======================================================

class VerticalBlock(AbstractBlock):
    '''
    Block to merge two other blocks vertically
    '''

    def __init__(self, top_block, bottom_block):
        AbstractBlock.__init__(self, None)
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
class CurrentTimesDistBlock(AbstractBlock):
    '''
    Detailed distribution for current RPS
    '''

    def __init__(self, screen):
        AbstractBlock.__init__(self, screen)
        self.current_codes = {}
        self.current_rps = 0
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
            line, quan = self.__format_line(current_times, quan)
            self.width = max(self.width, len(line))
            self.lines.append(line)
        self.lines.reverse()
        self.lines = [self.screen.markup.WHITE + 'Times for %s RPS:' % self.current_rps + self.screen.markup.RESET] \
                     + self.lines
        self.lines.append("")

        count_len = str(len(str(self.current_count)))
        tpl = ' %' + count_len + 'd %6.2f%%: Total'
        if self.current_count:
            self.lines.append(tpl % (self.current_count, 100))
        self.width = max(self.width, len(self.lines[0]))

    def __format_line(self, current_times, quan):
        ''' Format dist line '''
        left_line = ''
        if current_times:
            item = current_times.pop(0)[1]
            if self.current_count:
                perc = float(item['count']) / self.current_count
            else:
                perc = 1
            quan += perc
            # 30691    9.26%: 010  --  025       68.03%  <  025
            count_len = str(len(str(self.current_count)))
            timing_len = str(len(str(self.current_max_rt)))
            tpl = '  %' + count_len + 'd %6.2f%%: %' + timing_len + 'd -- %' + timing_len + 'd  %6.2f%% < %' + timing_len + 'd'
            data = (item['count'], perc * 100, item['from'], item['to'], quan * 100, item['to'])
            left_line = tpl % data
        return left_line, quan


# ======================================================

class CurrentHTTPBlock(AbstractBlock):
    ''' Http codes with highlight'''
    TITLE = 'HTTP for %s RPS:  '

    def __init__(self, screen):
        AbstractBlock.__init__(self, screen)
        self.times_dist = {}
        self.current_rps = 0
        self.total_count = 0
        self.highlight_codes = []


    def process_dist(self, rps, codes_dist):
        '''
        Analyze arrived codes distribution and highlight arrived
        '''
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
        self.lines = [self.screen.markup.WHITE + self.TITLE % self.current_rps + self.screen.markup.RESET]
        #self.width = len(self.lines[0])
        for code, count in sorted(self.times_dist.iteritems()):
            line = self.format_line(code, count)
            self.width = max(self.width, len(self.screen.markup.clean_markup(line)))
            self.lines.append(line)

    def format_line(self, code, count):
        ''' format line for display '''
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
        tpl = '  %' + count_len + 'd %6.2f%%: %s %s'
        data = (count, perc * 100, code, code_desc)
        left_line = tpl % data

        if code in self.highlight_codes:
            code = str(code)
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
    ''' NET codes with highlight'''
    TITLE = ' NET for %s RPS:  '

    def add_second(self, data):
        rps = data.overall.planned_requests
        codes_dist = copy.deepcopy(data.overall.net_codes)
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
        tpl = '  %' + count_len + 'd %6.2f%%: %s %s'
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
    ''' Total test quantiles '''

    def __init__(self, screen):
        AbstractBlock.__init__(self, screen)
        self.total_count = 0
        self.current_max_rt = 0
        self.quantiles = {}

    def add_second(self, data):
        self.quantiles = data.cumulative.quantiles

    def render(self):
        self.lines = []
        for quant in sorted(self.quantiles):
            line = self.__format_line(quant, self.quantiles[quant])
            self.width = max(self.width, len(line))
            self.lines.append(line)

        self.lines.reverse()
        self.lines = [self.screen.markup.WHITE + 'Cumulative Percentiles:' + self.screen.markup.RESET] + self.lines
        self.width = max(self.width, len(self.screen.markup.clean_markup(self.lines[0])))

    def __format_line(self, quan, timing):
        ''' Format line '''
        timing_len = str(len(str(self.current_max_rt)))
        tpl = '   %3d%% < %' + timing_len + 'd ms'
        data = (quan, timing)
        left_line = tpl % data
        return left_line


# ======================================================


class AnswSizesBlock(AbstractBlock):
    ''' Answer sizes, if available '''

    def __init__(self, screen):
        AbstractBlock.__init__(self, screen)
        self.sum_in = 0
        self.current_rps = -1
        self.sum_out = 0
        self.count = 0
        self.header = screen.markup.WHITE + 'Request/Response Sizes:' + screen.markup.RESET
        self.cur_count = 0
        self.cur_in = 0
        self.cur_out = 0

    def render(self):
        self.lines = [self.header]
        if self.count:
            self.lines.append("   Avg Request at %s RPS: %d bytes" % (self.current_rps, self.sum_out / self.count))
            self.lines.append("  Avg Response at %s RPS: %d bytes" % (self.current_rps, self.sum_in / self.count))
            self.lines.append("")
        if self.cur_count:
            self.lines.append("   Last Avg Request: %d bytes" % (self.cur_out / self.cur_count))
            self.lines.append("  Last Avg Response: %d bytes" % (self.cur_in / self.cur_count))
        else:
            self.lines.append("")
            self.lines.append("")
        for line in self.lines:
            self.width = max(self.width, len(self.screen.markup.clean_markup(line)))

    def add_second(self, data):
        if data.overall.planned_requests != self.current_rps:
            self.current_rps = data.overall.planned_requests
            self.sum_in = 0
            self.sum_out = 0
            self.count = 0

        self.count += data.overall.RPS
        self.sum_in += data.overall.input
        self.sum_out += data.overall.output

        self.cur_in = data.overall.input
        self.cur_out = data.overall.output
        self.cur_count = data.overall.RPS


# ======================================================


class AvgTimesBlock(AbstractBlock):
    ''' Average times breakdown '''

    def __init__(self, screen):
        AbstractBlock.__init__(self, screen)
        self.rps_connect = 0
        self.rps_send = 0
        self.rps_latency = 0
        self.rps_receive = 0
        self.rps_overall = 0
        self.rps_count = 0
        self.current_rps = 0

        self.all_connect = 0
        self.all_send = 0
        self.all_latency = 0
        self.all_receive = 0
        self.all_overall = 0
        self.all_count = 0

        self.last_connect = 0
        self.last_send = 0
        self.last_latency = 0
        self.last_receive = 0
        self.last_overall = 0
        self.last_count = 0

        self.header = 'Avg Times (all / %s RPS / last):'

    def add_second(self, data):
        if self.current_rps != data.overall.planned_requests:
            self.current_rps = data.overall.planned_requests
            self.rps_connect = 0
            self.rps_send = 0
            self.rps_latency = 0
            self.rps_receive = 0
            self.rps_overall = 0
            self.rps_count = 0

        self.rps_connect += data.overall.avg_connect_time * data.overall.RPS
        self.rps_send += data.overall.avg_send_time * data.overall.RPS
        self.rps_latency += data.overall.avg_latency * data.overall.RPS
        self.rps_receive += data.overall.avg_receive_time * data.overall.RPS
        self.rps_overall += data.overall.avg_response_time * data.overall.RPS
        self.rps_count += data.overall.RPS

        self.all_connect += data.overall.avg_connect_time * data.overall.RPS
        self.all_send += data.overall.avg_send_time * data.overall.RPS
        self.all_latency += data.overall.avg_latency * data.overall.RPS
        self.all_receive += data.overall.avg_receive_time * data.overall.RPS
        self.all_overall += data.overall.avg_response_time * data.overall.RPS
        self.all_count += data.overall.RPS

        self.last_connect = data.overall.avg_connect_time * data.overall.RPS
        self.last_send = data.overall.avg_send_time * data.overall.RPS
        self.last_latency = data.overall.avg_latency * data.overall.RPS
        self.last_receive = data.overall.avg_receive_time * data.overall.RPS
        self.last_overall = data.overall.avg_response_time * data.overall.RPS
        self.last_count = data.overall.RPS

    def render(self):
        self.lines = [self.screen.markup.WHITE + self.header % self.current_rps + self.screen.markup.RESET]
        if self.last_count:
            len_all = str(
                len(str(max([self.all_connect, self.all_latency, self.all_overall, self.all_receive, self.all_send]))))
            len_rps = str(
                len(str(max([self.rps_connect, self.rps_latency, self.rps_overall, self.rps_receive, self.rps_send]))))
            len_last = str(len(
                str(max([self.last_connect, self.last_latency, self.last_overall, self.last_receive, self.last_send]))))
            tpl = "%" + len_all + "d / %" + len_rps + "d / %" + len_last + "d"
            self.lines.append("  Overall: " + tpl % (
                float(self.all_overall) / self.all_count, float(self.rps_overall) / self.rps_count,
                float(self.last_overall) / self.last_count))
            self.lines.append("  Connect: " + tpl % (
                float(self.all_connect) / self.all_count, float(self.rps_connect) / self.rps_count,
                float(self.last_connect) / self.last_count))
            self.lines.append("     Send: " + tpl % (
                float(self.all_send) / self.all_count, float(self.rps_send) / self.rps_count,
                float(self.last_send) / self.last_count))
            self.lines.append("  Latency: " + tpl % (
                float(self.all_latency) / self.all_count, float(self.rps_latency) / self.rps_count,
                float(self.last_latency) / self.last_count))
            self.lines.append("  Receive: " + tpl % (
                float(self.all_receive) / self.all_count, float(self.rps_receive) / self.rps_count,
                float(self.last_receive) / self.last_count))
        else:
            self.lines.append("")
            self.lines.append("")
            self.lines.append("")
            self.lines.append("")
            self.lines.append("")
        for line in self.lines:
            self.width = max(self.width, len(self.screen.markup.clean_markup(line)))


# ======================================================


class CasesBlock(AbstractBlock):
    '''     Cases info    '''

    def __init__(self, screen):
        AbstractBlock.__init__(self, screen)
        self.cases = {}
        self.count = 0
        self.header = "Cumulative Cases Info:"
        self.highlight_cases = []
        self.max_case_len = 0

    def add_second(self, data):
        self.highlight_cases = []
        for name, case in data.cases.iteritems():
            #decode symbols to utf-8 in order to support cyrillic symbols in cases
            name = name.decode('utf-8')
            self.highlight_cases.append(name)
            if not name in self.cases.keys():
                self.cases[name] = [0, 0]
                self.max_case_len = max(self.max_case_len, len(name))
            self.cases[name][0] += case.RPS
            self.cases[name][1] += case.avg_response_time * case.RPS
            self.count += case.RPS

    def render(self):
        self.lines = [self.screen.markup.WHITE + self.header + self.screen.markup.RESET]
        tpl = "  %s: %" + str(len(str(self.count))) + "d %5.2f%% / avg %.1f ms"
        for name, (count, resp_time) in sorted(self.cases.iteritems()):
            line = tpl % (" " * (self.max_case_len - len(name)) + name, count, 100 * float(count) / self.count,
                          float(resp_time) / count)
            if name in self.highlight_cases:
                self.lines.append(self.screen.markup.CYAN + line + self.screen.markup.RESET)
            else:
                self.lines.append(line)

        for line in self.lines:
            self.width = max(self.width, len(self.screen.markup.clean_markup(line)))
