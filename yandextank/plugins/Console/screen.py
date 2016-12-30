''' Classes to build full console screen '''
import fcntl
import logging
import math
import os
import struct
import termios
from collections import defaultdict

from ...common import util


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
            sizes = struct.unpack(
                'hh', fcntl.ioctl(file_d, termios.TIOCGWINSZ, '1234'))
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
        self.left_panel_width = self.term_width - self.right_panel_width - len(
            self.RIGHT_PANEL_SEPARATOR)

        block1 = VerticalBlock(CurrentHTTPBlock(self), CurrentNetBlock(self))
        block2 = VerticalBlock(block1, CasesBlock(self))
        block3 = VerticalBlock(block2, CurrentQuantilesBlock(self))
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
                    right_line = right_line[:self.
                                            right_panel_width] + self.markup.RESET
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
                        line += block_line + ' ' * (
                            block.width -
                            len(self.markup.clean_markup(block_line)))
                        had_lines = True
                    else:
                        line += ' ' * block.width
                    line += space
                lines.append(line)
                # lines.append(".  " * (1 + self.left_panel_width / 3))
                # lines.append("")
        return lines

    def render_screen(self):
        '''        Main method to render screen view        '''
        self.term_width, self.term_height = get_terminal_size()
        self.log.debug(
            "Terminal size: %sx%s", self.term_width, self.term_height)
        self.right_panel_width = int(
            (self.term_width - len(self.RIGHT_PANEL_SEPARATOR)) *
            (float(self.info_panel_percent) / 100)) - 1
        if self.right_panel_width > 0:
            self.left_panel_width = self.term_width - \
                self.right_panel_width - len(self.RIGHT_PANEL_SEPARATOR) - 2
        else:
            self.right_panel_width = 0
            self.left_panel_width = self.term_width - 1
        self.log.debug(
            "Left/right panels width: %s/%s", self.left_panel_width,
            self.right_panel_width)

        widget_output = []
        if self.right_panel_width:
            widget_output = []
            self.log.debug("There are %d info widgets" % len(self.info_widgets))
            for index, widget in sorted(
                    self.info_widgets.iteritems(),
                    key=lambda item: (item[1].get_index(), item[0])):
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
                        left_line = left_line[:self.
                                              left_panel_width] + self.markup.RESET

                left_line += (
                    ' ' * (self.left_panel_width - len(left_line_plain)))
                line += left_line
            else:
                line += ' ' * self.left_panel_width
            if self.right_panel_width:
                line += self.markup.WHITE
                line += self.RIGHT_PANEL_SEPARATOR
                line += self.markup.RESET
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
    Current times distribution
    '''

    def __init__(self, screen):
        AbstractBlock.__init__(self, screen)
        self.current_rps = 0
        self.hist = []
        self.width = 0

    def add_second(self, data):
        self.current_rps = data["overall"]["interval_real"]["len"]
        self.hist = zip(
            data["overall"]["interval_real"]["hist"]["bins"],
            data["overall"]["interval_real"]["hist"]["data"], )

    def render(self):
        self.lines = []
        for bin, cnt in self.hist:
            line = "{cnt}({pct:.2%}) < {bin} ms".format(
                cnt=cnt,
                pct=cnt / float(self.current_rps),
                bin=bin / 1000, )
            self.width = max(self.width, len(line))
            self.lines.append(line)
        self.lines.reverse()
        self.lines = [
            self.screen.markup.GREEN + 'RPS: %s' % self.current_rps +
            self.screen.markup.RESET, '', 'Times distribution:'
        ] + self.lines
        self.lines.append("")

        self.width = max(self.width, len(self.lines[0]))


# ======================================================


class CurrentHTTPBlock(AbstractBlock):
    ''' Http codes with highlight'''
    TITLE = 'HTTP codes:'

    def __init__(self, screen):
        AbstractBlock.__init__(self, screen)
        self.times_dist = defaultdict(int)
        self.total_count = 0
        self.highlight_codes = []

    def add_second(self, data):
        codes_dist = data["overall"]["proto_code"]["count"]

        self.log.debug("Arrived codes data: %s", codes_dist)
        self.highlight_codes = []

        for code, count in codes_dist.iteritems():
            self.total_count += count
            self.highlight_codes.append(code)
            self.times_dist[code] += count

        self.log.debug("Current codes dist: %s", self.times_dist)

    def render(self):
        self.lines = [
            self.screen.markup.WHITE + self.TITLE + self.screen.markup.RESET
        ]
        for code, count in sorted(self.times_dist.iteritems()):
            line = self.format_line(code, count)
            self.width = max(
                self.width, len(self.screen.markup.clean_markup(line)))
            self.lines.append(line)

    def format_line(self, code, count):
        ''' format line for display '''
        if self.total_count:
            perc = float(count) / self.total_count
        else:
            perc = 1
        # 11083   5.07%: 304 Not Modified
        count_len = str(len(str(self.total_count)))
        if int(code) in util.HTTP:
            code_desc = util.HTTP[int(code)]
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


class CurrentNetBlock(AbstractBlock):
    ''' NET codes with highlight'''
    TITLE = 'NET codes:'

    def __init__(self, screen):
        AbstractBlock.__init__(self, screen)
        self.times_dist = defaultdict(int)
        self.total_count = 0

    def add_second(self, data):
        net_dist = data["overall"]["net_code"]["count"]

        self.log.debug("Arrived net codes data: %s", net_dist)
        self.highlight_codes = []

        for code, count in net_dist.iteritems():
            self.total_count += count
            self.highlight_codes.append(code)
            self.times_dist[code] += count

        self.log.debug("Current net codes dist: %s", self.times_dist)

    def format_line(self, code, count):
        if self.total_count:
            perc = float(count) / self.total_count
        else:
            perc = 1
        # 11083   5.07%: 304 Not Modified
        count_len = str(len(str(self.total_count)))
        if int(code) in util.NET:
            code_desc = util.NET[int(code)]
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

    def render(self):
        self.lines = [
            self.screen.markup.WHITE + self.TITLE + self.screen.markup.RESET
        ]
        for code, count in sorted(self.times_dist.iteritems()):
            line = self.format_line(code, count)
            self.width = max(
                self.width, len(self.screen.markup.clean_markup(line)))
            self.lines.append(line)


# ======================================================


class CurrentQuantilesBlock(AbstractBlock):
    ''' Current test quantiles '''

    def __init__(self, screen):
        AbstractBlock.__init__(self, screen)
        self.total_count = 0
        self.current_max_rt = 0
        self.quantiles = {}

    def add_second(self, data):
        self.quantiles = {
            k: v
            for k, v in zip(
                data["overall"]["interval_real"]["q"]["q"], data["overall"][
                    "interval_real"]["q"]["value"])
        }

    def render(self):
        self.lines = []
        for quant in sorted(self.quantiles):
            line = self.__format_line(quant, self.quantiles[quant])
            self.width = max(self.width, len(line))
            self.lines.append(line)

        self.lines.reverse()
        self.lines = [
            self.screen.markup.WHITE + 'Current Percentiles:' +
            self.screen.markup.RESET
        ] + self.lines
        self.width = max(
            self.width, len(self.screen.markup.clean_markup(self.lines[0])))

    def __format_line(self, quan, timing):
        ''' Format line '''
        timing_len = str(len(str(self.current_max_rt)))
        tpl = '   %3s%% < %' + timing_len + '.2f ms'
        data = (quan, timing / 1000.0)
        left_line = tpl % data
        return left_line


# ======================================================


class AnswSizesBlock(AbstractBlock):
    ''' Answer sizes, if available '''

    def __init__(self, screen):
        AbstractBlock.__init__(self, screen)
        self.sum_in = 0
        self.sum_out = 0
        self.count = 0
        self.header = screen.markup.WHITE + 'Request/Response Sizes:' + screen.markup.RESET
        self.cur_count = 0
        self.cur_in = 0
        self.cur_out = 0

    def render(self):
        self.lines = [self.header]
        if self.count:
            self.lines.append(
                "   Avg Request: %d bytes" % (self.sum_out / self.count))
            self.lines.append(
                "  Avg Response: %d bytes" % (self.sum_in / self.count))
            self.lines.append("")
        if self.cur_count:
            self.lines.append(
                "   Last Avg Request: %d bytes" %
                (self.cur_out / self.cur_count))
            self.lines.append(
                "  Last Avg Response: %d bytes" %
                (self.cur_in / self.cur_count))
        else:
            self.lines.append("")
            self.lines.append("")
        for line in self.lines:
            self.width = max(
                self.width, len(self.screen.markup.clean_markup(line)))

    def add_second(self, data):

        self.cur_in = data["overall"]["size_out"]["total"]
        self.cur_out = data["overall"]["size_out"]["total"]
        self.cur_count = data["overall"]["interval_real"]["len"]

        self.count += self.cur_count
        self.sum_in += self.cur_in
        self.sum_out += self.cur_out


# ======================================================


class AvgTimesBlock(AbstractBlock):
    ''' Average times breakdown '''

    def __init__(self, screen):
        AbstractBlock.__init__(self, screen)

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

        self.header = 'Avg Times (all / last):'

    def add_second(self, data):
        count = data["overall"]["interval_real"]["len"]
        self.last_connect = data["overall"]["connect_time"]["total"]
        self.last_send = data["overall"]["send_time"]["total"]
        self.last_latency = data["overall"]["latency"]["total"]
        self.last_receive = data["overall"]["receive_time"]["total"]
        self.last_overall = data["overall"]["interval_real"]["total"]
        self.last_count = count

        self.all_connect += self.last_connect
        self.all_send += self.last_send
        self.all_latency += self.last_latency
        self.all_receive += self.last_receive
        self.all_overall += self.last_overall
        self.all_count += count

    def render(self):
        self.lines = [
            self.screen.markup.WHITE + self.header + self.screen.markup.RESET
        ]
        if self.last_count:
            len_all = str(
                len(
                    str(
                        max([
                            self.all_connect, self.all_latency,
                            self.all_overall, self.all_receive, self.all_send
                        ]))))
            len_last = str(
                len(
                    str(
                        max([
                            self.last_connect, self.last_latency,
                            self.last_overall, self.last_receive, self.last_send
                        ]))))
            tpl = "%" + len_all + "d / %" + len_last + "d"
            self.lines.append(
                "  Overall: " + tpl % (
                    float(self.all_overall) / self.all_count, float(
                        self.last_overall) / self.last_count))
            self.lines.append(
                "  Connect: " + tpl % (
                    float(self.all_connect) / self.all_count, float(
                        self.last_connect) / self.last_count))
            self.lines.append(
                "     Send: " + tpl % (
                    float(self.all_send) / self.all_count, float(
                        self.last_send) / self.last_count))
            self.lines.append(
                "  Latency: " + tpl % (
                    float(self.all_latency) / self.all_count, float(
                        self.last_latency) / self.last_count))
            self.lines.append(
                "  Receive: " + tpl % (
                    float(self.all_receive) / self.all_count, float(
                        self.last_receive) / self.last_count))
        else:
            self.lines.append("")
            self.lines.append("")
            self.lines.append("")
            self.lines.append("")
            self.lines.append("")
        for line in self.lines:
            self.width = max(
                self.width, len(self.screen.markup.clean_markup(line)))


# ======================================================


class CasesBlock(AbstractBlock):
    '''     Cases info    '''

    def __init__(self, screen):
        AbstractBlock.__init__(self, screen)
        self.cases = {}
        self.count = 0
        self.header = "Cumulative Cases Info:"
        self.max_case_len = 0

    def add_second(self, data):
        tagged = data["tagged"]
        for tag_name, tag_data in tagged.iteritems():
            # decode symbols to utf-8 in order to support cyrillic symbols in
            # cases
            name = tag_name.decode('utf-8')
            if name not in self.cases.keys():
                self.cases[name] = [0, 0]
                self.max_case_len = max(self.max_case_len, len(name))
            rps = tag_data["interval_real"]["len"]
            self.cases[name][0] += rps
            self.cases[name][1] += tag_data["interval_real"]["total"] / 1000

    def render(self):
        self.lines = [
            self.screen.markup.WHITE + self.header + self.screen.markup.RESET
        ]
        total_count = sum(case[0] for case in self.cases.values())
        tpl = "  %s: %" + str(len(str(total_count))) + "d %5.2f%% / avg %.1f ms"
        for name, (count, resp_time) in sorted(self.cases.iteritems()):
            line = tpl % (
                " " * (self.max_case_len - len(name)) + name, count,
                100 * float(count) / total_count, float(resp_time) / count)
            self.lines.append(line)

        for line in self.lines:
            self.width = max(
                self.width, len(self.screen.markup.clean_markup(line)))
