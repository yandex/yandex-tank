# -*- coding: utf-8 -*-
''' Classes to build full console screen '''
import fcntl
import logging
import os
import struct
import termios
import time
import bisect
from collections import defaultdict
import pandas as pd

from ...common import util


def get_terminal_size():
    '''
    Gets width and height of terminal viewport
    '''
    default_size = (30, 120)
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


def safe_div(summ, count):
    if count == 0:
        return 0
    else:
        return float(summ) / count


def str_len(n):
    return len(str(n))


def avg_from_dict(src):
    result = {}
    count = src['count']
    for k, v in src.items():
        if k != 'count':
            result[k] = safe_div(v, count)
    return result


def krutilka():
    pos = 0
    chars = "|/-\\"
    while True:
        yield chars[pos]
        pos += 1
        if pos >= len(chars):
            pos = 0


def try_color(old, new, markup):
    order = [
        markup.WHITE, markup.GREEN, markup.CYAN,
        markup.YELLOW, markup.MAGENTA, markup.RED]
    if not old:
        return new
    else:
        if order.index(old) > order.index(new):
            return old
        else:
            return new


def combine_codes(tag_data, markup):
    net_err, http_err = 0, 0
    color = ''
    net_codes = tag_data['net_code']['count']
    for code, count in sorted(net_codes.items()):
        if count > 0:
            if int(code) == 0:
                continue
            elif int(code) == 314:
                color = try_color(color, markup.MAGENTA, markup)
                net_err += count
            else:
                color = try_color(color, markup.RED, markup)
                net_err += count
    http_codes = tag_data['proto_code']['count']
    for code, count in sorted(http_codes.items()):
        if count > 0:
            if 100 <= int(code) <= 299:
                color = try_color(color, markup.GREEN, markup)
            elif 300 <= int(code) <= 399:
                color = try_color(color, markup.CYAN, markup)
            elif 400 <= int(code) <= 499:
                color = try_color(color, markup.YELLOW, markup)
                http_err += count
            elif 500 <= int(code) <= 599:
                color = try_color(color, markup.RED, markup)
                http_err += count
            else:
                color = try_color(color, markup.MAGENTA, markup)
                http_err += count
    return (net_err, http_err, color)


class TableFormatter(object):
    def __init__(self, template, delimiters, reshape_delay=5):
        self.log = logging.getLogger(__name__)
        self.template = template
        self.delimiters = delimiters
        self.default_final = '{{{:}:>{len}}}'
        self.last_reshaped = time.time()
        self.old_shape = {}
        self.reshape_delay = reshape_delay

    def __delimiter_gen(self):
        for d in self.delimiters:
            yield d
        while True:
            yield self.delimiters[-1]

    def __prepare(self, data):
        prepared = []
        shape = {}
        for line in data:
            new = {}
            for f in line:
                if f in self.template:
                    new[f] = self.template[f]['tpl'].format(line[f])
                    if f not in shape:
                        shape[f] = len(new[f])
                    else:
                        shape[f] = max(shape[f], len(new[f]))
            prepared.append(new)
        return (prepared, shape)

    def __update_shape(self, shape):
        def change_shape():
            self.last_reshaped = time.time()
            self.old_shape = shape
        if set(shape.keys()) != set(self.old_shape.keys()):
            change_shape()
            return shape
        else:
            for f in shape:
                if shape[f] > self.old_shape[f]:
                    change_shape()
                    return shape
                elif shape[f] < self.old_shape[f]:
                    if time.time() > (self.last_reshaped + self.reshape_delay):
                        change_shape()
                        return shape
        return self.old_shape

    def render_table(self, data, fields):
        prepared, shape = self.__prepare(data)
        headers = {}
        for f in shape:
            if 'header' in self.template[f]:
                headers[f] = self.template[f]['header']
                shape[f] = max(shape[f], len(headers[f]))
            else:
                headers[f] = ''
        shape = self.__update_shape(shape)
        has_headers = any(headers.values())
        delimiter_gen = self.__delimiter_gen()
        row_tpl = ''
        for num, field in enumerate(fields):
            if 'final' in self.template[field]:
                final = self.template[field]['final']
            else:
                final = self.default_final
            row_tpl += final.format(field, len=shape[field])
            if num < len(fields) - 1:
                row_tpl += next(delimiter_gen)
        result = []
        if has_headers:
            result.append(
                (row_tpl.format(**headers),))
        for line in prepared:
            result.append(
                (row_tpl.format(**line),))
        return result


class Sparkline(object):
    def __init__(self, window):
        self.log = logging.getLogger(__name__)
        self.data = {}
        self.window = window
        self.active_seconds = []
        self.ticks = '_▁▂▃▄▅▆▇'

    def recalc_active(self, ts):
        if not self.active_seconds:
            self.active_seconds.append(ts)
            self.data[ts] = {}
        if ts not in self.active_seconds:
            if ts > max(self.active_seconds):
                for i in range(max(self.active_seconds) + 1, ts + 1):
                    self.active_seconds.append(i)
                    self.active_seconds.sort()
                    self.data[i] = {}
        while len(self.active_seconds) > self.window:
            self.active_seconds.pop(0)
        for sec in tuple(self.data.keys()):
            if sec not in self.active_seconds:
                self.data.pop(sec)

    def get_key_data(self, key):
        result = []
        if not self.active_seconds:
            return None
        for sec in self.active_seconds:
            if key in self.data[sec]:
                result.append(self.data[sec][key])
            else:
                result.append(('', 0))
        return result

    def add(self, ts, key, value, color=''):
        if ts not in self.data:
            self.recalc_active(ts)
        if ts < min(self.active_seconds):
            self.log.warning('Sparkline got outdated second %s, oldest in list %s', ts, min(self.active_seconds))
            return
        value = max(value, 0)
        self.data[ts][key] = (color, value)

    def get_sparkline(self, key, baseline='zero', spark_len='auto', align='right'):
        if spark_len == 'auto':
            spark_len = self.window
        elif spark_len <= 0:
            return ''
        key_data = self.get_key_data(key)
        if not key_data:
            return ''
        active_data = key_data[-spark_len:]
        result = []
        if active_data:
            values = [i[1] for i in active_data]
            if baseline == 'zero':
                min_val = 0
                step = float(max(values)) / len(self.ticks)
            elif baseline == 'min':
                min_val = min(values)
                step = float(max(values) - min_val) / len(self.ticks)
            ranges = [step * i for i in range(len(self.ticks) + 1)]
            for color, value in active_data:
                if value <= 0:
                    tick = ' '
                else:
                    rank = bisect.bisect_left(ranges, value) - 1
                    rank = max(rank, 0)
                    rank = min(rank, len(self.ticks) - 1)
                    tick = self.ticks[rank]
                result.append(color)
                result.append(tick)
        space = ' ' * (spark_len - len(active_data))
        if align == 'right':
            result = [space] + result
        elif align == 'left':
            result = result + [space]
        return result


class Screen(object):
    '''     Console screen renderer class    '''
    RIGHT_PANEL_SEPARATOR = ' . '

    def __init__(self, info_panel_width, markup_provider, **kwargs):
        self.log = logging.getLogger(__name__)
        self.info_panel_percent = int(info_panel_width)
        self.info_widgets = {}
        self.markup = markup_provider
        self.term_height = 60
        self.term_width = 120
        self.right_panel_width = 10
        self.left_panel_width = self.term_width - self.right_panel_width - len(
            self.RIGHT_PANEL_SEPARATOR)
        cases_args = dict(
            [(k, v)
                for k, v in kwargs.items()
                if k in ['cases_sort_by', 'cases_max_spark', 'max_case_len']]
        )
        times_args = {'times_max_spark': kwargs['times_max_spark']}
        sizes_args = {'sizes_max_spark': kwargs['sizes_max_spark']}

        codes_block = VerticalBlock(CurrentHTTPBlock(self), CurrentNetBlock(self), self)
        times_block = VerticalBlock(AnswSizesBlock(self, **sizes_args), AvgTimesBlock(self, **times_args), self)
        top_block = VerticalBlock(codes_block, times_block, self)
        general_block = HorizontalBlock(PercentilesBlock(self), top_block, self)
        overall_block = VerticalBlock(RPSBlock(self), general_block, self)
        final_block = VerticalBlock(overall_block, CasesBlock(self, **cases_args), self)

        self.left_panel = final_block

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

    def __truncate(self, line_arr, max_width):
        '''  Cut tuple of line chunks according to it's wisible lenght  '''
        def is_space(chunk):
            return all([True if i == ' ' else False for i in chunk])

        def is_empty(chunks, markups):
            result = []
            for chunk in chunks:
                if chunk in markups:
                    result.append(True)
                elif is_space(chunk):
                    result.append(True)
                else:
                    result.append(False)
            return all(result)
        left = max_width
        result = ''
        markups = self.markup.get_markup_vars()
        for num, chunk in enumerate(line_arr):
            if chunk in markups:
                result += chunk
            else:
                if left > 0:
                    if len(chunk) <= left:
                        result += chunk
                        left -= len(chunk)
                    else:
                        leftover = (chunk[left:],) + line_arr[num + 1:]
                        was_cut = not is_empty(leftover, markups)
                        if was_cut:
                            result += chunk[:left - 1] + self.markup.RESET + '…'
                        else:
                            result += chunk[:left]
                        left = 0
        return result

    def __render_left_panel(self):
        ''' Render left blocks '''
        self.log.debug("Rendering left blocks")
        left_block = self.left_panel
        left_block.render()
        blank_space = self.left_panel_width - left_block.width

        lines = []
        pre_space = ' ' * int(blank_space / 2)
        if not left_block.lines:
            lines = [(''), (self.markup.RED + 'BROKEN LEFT PANEL' + self.markup.RESET)]
        else:
            while self.left_panel.lines:
                src_line = self.left_panel.lines.pop(0)
                line = pre_space + self.__truncate(src_line, self.left_panel_width)
                post_space = ' ' * (self.left_panel_width - len(self.markup.clean_markup(line)))
                line += post_space + self.markup.RESET
                lines.append(line)
        return lines

    def render_screen(self):
        '''        Main method to render screen view        '''
        self.term_width, self.term_height = get_terminal_size()
        self.log.debug(
            "Terminal size: %sx%s", self.term_width, self.term_height)
        self.right_panel_width = int(
            (self.term_width - len(self.RIGHT_PANEL_SEPARATOR))
            * (float(self.info_panel_percent) / 100)) - 1
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
                    self.info_widgets.items(),
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

                left_line += (
                    ' ' * (self.left_panel_width - len(left_line_plain)))
                line += left_line
            else:
                line += ' ' * self.left_panel_width
            if self.right_panel_width:
                line += self.markup.RESET
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
        while index in self.info_widgets:
            index += 1
        self.info_widgets[widget.get_index()] = widget

    def add_second_data(self, data):
        '''
        Notification method about new aggregator data
        '''
        self.left_panel.add_second(data)


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

    def fill_rectangle(self, prepared):
        '''  Right-pad lines of block to equal width  '''
        result = []
        width = max([self.clean_len(line) for line in prepared])
        for line in prepared:
            spacer = ' ' * (width - self.clean_len(line))
            result.append(line + (self.screen.markup.RESET, spacer))
        return (width, result)

    def clean_len(self, line):
        '''  Calculate wisible length of string  '''
        if isinstance(line, str):
            return len(self.screen.markup.clean_markup(line))
        elif isinstance(line, tuple) or isinstance(line, list):
            markups = self.screen.markup.get_markup_vars()
            length = 0
            for i in line:
                if i not in markups:
                    length += len(i)
            return length

    def render(self):
        '''
        Render method, fills .lines and .width properties with rendered data
        '''
        raise RuntimeError("Abstract method needs to be overridden")


class HorizontalBlock(AbstractBlock):
    '''
    Block to merge two other blocks horizontaly
    '''

    def __init__(self, left_block, right_block, screen):
        AbstractBlock.__init__(self, screen)
        self.left = left_block
        self.right = right_block
        self.separator = '  . '

    def render(self, expected_width=None):
        if not expected_width:
            expected_width = self.screen.left_panel_width

        def get_line(source, num):
            if num >= len(source.lines):
                return (' ' * source.width,)
            else:
                source_line = source.lines[n]
                spacer = ' ' * (source.width - self.clean_len(source_line))
                return source_line + (spacer,)
        self.left.render(expected_width=expected_width)
        right_width_limit = expected_width - self.left.width - len(self.separator)
        self.right.render(expected_width=right_width_limit)
        self.height = max(len(self.left.lines), len(self.right.lines))
        self.width = self.left.width + self.right.width + len(self.separator)

        self.lines = []

        for n in range(self.height):
            self.lines.append(
                get_line(self.left, n) + (self.separator,) + get_line(self.right, n)
            )
        self.lines.append((' ' * self.width,))

    def add_second(self, data):
        self.left.add_second(data)
        self.right.add_second(data)


class VerticalBlock(AbstractBlock):
    '''
    Block to merge two other blocks vertically
    '''

    def __init__(self, top_block, bottom_block, screen):
        AbstractBlock.__init__(self, screen)
        self.top = top_block
        self.bottom = bottom_block

    def render(self, expected_width=None):
        if not expected_width:
            expected_width = self.screen.left_panel_width

        self.top.render(expected_width=expected_width)
        self.bottom.render(expected_width=expected_width)
        self.width = max(self.top.width, self.bottom.width)

        self.lines = []
        for line in self.top.lines:
            spacer = ' ' * (self.width - self.top.width)
            self.lines.append(line + (spacer,))

        if self.top.lines and self.bottom.lines:
            spacer = ' ' * self.width
            self.lines.append((spacer,))

        for line in self.bottom.lines:
            spacer = ' ' * (self.width - self.bottom.width)
            self.lines.append(line + (spacer,))

    def add_second(self, data):
        self.top.add_second(data)
        self.bottom.add_second(data)


class RPSBlock(AbstractBlock):
    ''' Actual RPS sparkline '''

    def __init__(self, screen):
        AbstractBlock.__init__(self, screen)
        self.begin_tpl = 'Data delay: {delay}s, RPS: {rps:>3,} '
        self.sparkline = Sparkline(180)
        self.last_count = 0
        self.last_second = None

    def add_second(self, data):
        count = data['overall']['interval_real']['len']
        self.last_count = count
        ts = data['ts']
        self.last_second = ts
        self.sparkline.add(ts, 'rps', count)

    def render(self, expected_width=None):
        if self.last_second:
            delay = int(time.time() - self.last_second)
        else:
            delay = ' - '
        line_start = self.begin_tpl.format(rps=self.last_count, delay=delay)
        spark_len = expected_width - len(line_start) - 2

        spark = self.sparkline.get_sparkline('rps', spark_len=spark_len)
        prepared = [(self.screen.markup.WHITE, line_start, ' ') + tuple(spark) + (self.screen.markup.RESET,)]
        self.width, self.lines = self.fill_rectangle(prepared)


class PercentilesBlock(AbstractBlock):
    ''' Aggregated percentiles '''

    def __init__(self, screen):
        AbstractBlock.__init__(self, screen)
        self.title = 'Percentiles (all/last 1m/last), ms:'
        self.overall = None
        self.width = 10
        self.last_ts = None
        self.last_min = {}
        self.quantiles = [10, 20, 30, 40, 50, 60, 70, 75, 80, 85, 90, 95, 99, 99.5, 100]
        template = {
            'quantile': {'tpl': '{:>.1f}%'},
            'all':      {'tpl': '{:>,.1f}'},  # noqa: E241
            'last_1m':  {'tpl': '{:>,.1f}'},  # noqa: E241
            'last':     {'tpl': '{:>,.1f}'}   # noqa: E241
        }
        delimiters = [' <  ', '  ']
        self.formatter = TableFormatter(template, delimiters)

    def add_second(self, data):
        incoming_hist = data['overall']['interval_real']['hist']
        ts = data['ts']
        self.precise_quantiles = {
            q: float(v) / 1000
            for q, v in zip(
                data["overall"]["interval_real"]["q"]["q"],
                data["overall"]["interval_real"]["q"]["value"])
        }
        dist = pd.Series(incoming_hist['data'], index=incoming_hist['bins'])
        if self.overall is None:
            self.overall = dist
        else:
            self.overall = self.overall.add(dist, fill_value=0)
        for second in tuple(self.last_min.keys()):
            if ts - second > 60:
                self.last_min.pop(second)
        self.last_min[ts] = dist

    def __calc_percentiles(self):
        def hist_to_quant(histogram, quant):
            cumulative = histogram.cumsum()
            total = cumulative.max()
            positions = cumulative.searchsorted([float(i) / 100 * total for i in quant])
            quant_times = [cumulative.index[i] / 1000. for i in positions]
            return quant_times

        all_times = hist_to_quant(self.overall, self.quantiles)
        last_data = self.last_min[max(self.last_min.keys())]
        last_times = hist_to_quant(last_data, self.quantiles)
        # Check if we have precise data for last second quantiles instead of binned histogram
        for position, q in enumerate(self.quantiles):
            if q in self.precise_quantiles:
                last_times[position] = self.precise_quantiles[q]
        # Replace binned values with precise, if lower quantile bin happens to be
        # greater than upper quantile precise values
        for position in reversed(range(1, len(last_times))):
            if last_times[position - 1] > last_times[position]:
                last_times[position - 1] = last_times[position]
        last_1m = pd.Series()
        for ts, data in self.last_min.items():
            if last_1m.empty:
                last_1m = data
            else:
                last_1m = last_1m.add(data, fill_value=0)
        last_1m_times = hist_to_quant(last_1m, self.quantiles)
        quant_times = reversed(
            list(zip(self.quantiles, all_times, last_1m_times, last_times))
        )
        data = []
        for q, all_time, last_1m, last_time in quant_times:
            data.append({
                'quantile': q,
                'all': all_time,
                'last_1m': last_1m,
                'last': last_time
            })
        return data

    def render(self, expected_width=None):
        prepared = [(self.screen.markup.WHITE, self.title)]
        if self.overall is None:
            prepared.append(('',))
        else:
            data = self.__calc_percentiles()
            prepared += self.formatter.render_table(data, ['quantile', 'all', 'last_1m', 'last'])
        self.width, self.lines = self.fill_rectangle(prepared)


class CurrentHTTPBlock(AbstractBlock):
    ''' Http codes with highlight'''

    def __init__(self, screen):
        AbstractBlock.__init__(self, screen)
        self.overall_dist = defaultdict(int)
        self.title = 'HTTP codes: '
        self.total_count = 0
        template = {
            'count':       {'tpl': '{:>,}'},  # noqa: E241
            'last':        {'tpl': '+{:>,}'},  # noqa: E241
            'percent':     {'tpl': '{:>.2f}%'},  # noqa: E241
            'code':        {'tpl': '{:>3}', 'final': '{{{:}:<{len}}}'},  # noqa: E241
            'description': {'tpl': '{:<10}', 'final': '{{{:}:<{len}}}'}
        }
        delimiters = [' ', '  ', ' : ', ' ']
        self.formatter = TableFormatter(template, delimiters)

    def add_second(self, data):
        self.last_dist = data["overall"]["proto_code"]["count"]
        for code, count in self.last_dist.items():
            self.total_count += count
            self.overall_dist[code] += count

    def __code_color(self, code):
        colors = {(200, 299): self.screen.markup.GREEN,
                  (300, 399): self.screen.markup.CYAN,
                  (400, 499): self.screen.markup.YELLOW,
                  (500, 599): self.screen.markup.RED}
        if code in self.last_dist:
            for left, right in colors:
                if left <= int(code) <= right:
                    return colors[(left, right)]
            return self.screen.markup.MAGENTA
        else:
            return ''

    def __code_descr(self, code):
        if int(code) in util.HTTP:
            return util.HTTP[int(code)]
        else:
            return 'N/A'

    def render(self, expected_width=None):
        prepared = [(self.screen.markup.WHITE, self.title)]
        if not self.overall_dist:
            prepared.append(('',))
        else:
            data = []
            for code, count in sorted(self.overall_dist.items()):
                if code in self.last_dist:
                    last_count = self.last_dist[code]
                else:
                    last_count = 0
                data.append({
                    'count': count,
                    'last': last_count,
                    'percent': 100 * safe_div(count, self.total_count),
                    'code': code,
                    'description': self.__code_descr(code)
                })
            table = self.formatter.render_table(data, ['count', 'last', 'percent', 'code', 'description'])
            for num, line in enumerate(data):
                color = self.__code_color(line['code'])
                prepared.append((color, table[num][0]))
        self.width, self.lines = self.fill_rectangle(prepared)


class CurrentNetBlock(AbstractBlock):
    ''' NET codes with highlight'''

    def __init__(self, screen):
        AbstractBlock.__init__(self, screen)
        self.overall_dist = defaultdict(int)
        self.title = 'Net codes:'
        self.total_count = 0
        template = {
            'count':       {'tpl': '{:>,}'},  # noqa: E241
            'last':        {'tpl': '+{:>,}'},  # noqa: E241
            'percent':     {'tpl': '{:>.2f}%'},  # noqa: E241
            'code':        {'tpl': '{:>2}', 'final': '{{{:}:<{len}}}'},  # noqa: E241
            'description': {'tpl': '{:<10}', 'final': '{{{:}:<{len}}}'}
        }
        delimiters = [' ', '  ', ' : ', ' ']
        self.formatter = TableFormatter(template, delimiters)

    def add_second(self, data):
        self.last_dist = data["overall"]["net_code"]["count"]

        for code, count in self.last_dist.items():
            self.total_count += count
            self.overall_dist[code] += count

    def __code_descr(self, code):
        if int(code) in util.NET:
            return util.NET[int(code)]
        else:
            return 'N/A'

    def __code_color(self, code):
        if code in self.last_dist:
            if int(code) == 0:
                return self.screen.markup.GREEN
            elif int(code) == 314:
                return self.screen.markup.MAGENTA
            else:
                return self.screen.markup.RED
        else:
            return ''

    def render(self, expected_width=None):
        prepared = [(self.screen.markup.WHITE, self.title)]
        if not self.overall_dist:
            prepared.append(('',))
        else:
            data = []
            for code, count in sorted(self.overall_dist.items()):
                if code in self.last_dist:
                    last_count = self.last_dist[code]
                else:
                    last_count = 0
                data.append({
                    'count': count,
                    'last': last_count,
                    'percent': 100 * safe_div(count, self.total_count),
                    'code': code,
                    'description': self.__code_descr(code)
                })
            table = self.formatter.render_table(data, ['count', 'last', 'percent', 'code', 'description'])
            for num, line in enumerate(data):
                color = self.__code_color(line['code'])
                prepared.append((color, table[num][0]))
        self.width, self.lines = self.fill_rectangle(prepared)


class AnswSizesBlock(AbstractBlock):
    ''' Answer and response sizes, if available '''

    def __init__(self, screen, sizes_max_spark=120):
        AbstractBlock.__init__(self, screen)
        self.sparkline = Sparkline(sizes_max_spark)
        self.overall = {'count': 0, 'Response': 0, 'Request': 0}
        self.last = {'count': 0, 'Response': 0, 'Request': 0}
        self.title = 'Average Sizes (all/last), bytes:'
        template = {
            'name': {'tpl': '{:>}'},
            'avg': {'tpl': '{:>,.1f}'},
            'last_avg': {'tpl': '{:>,.1f}'}
        }
        delimiters = [': ', ' / ']
        self.formatter = TableFormatter(template, delimiters)

    def add_second(self, data):
        self.last['count'] = data["overall"]["interval_real"]["len"]
        self.last['Request'] = data["overall"]["size_out"]["total"]
        self.last['Response'] = data["overall"]["size_in"]["total"]

        self.overall['count'] += self.last['count']
        self.overall['Request'] += self.last['Request']
        self.overall['Response'] += self.last['Response']
        ts = data['ts']
        for direction in ['Request', 'Response']:
            self.sparkline.add(ts, direction, self.last[direction] / self.last['count'])

    def render(self, expected_width=None):
        prepared = [(self.screen.markup.WHITE, self.title)]
        if self.overall['count']:
            overall_avg = avg_from_dict(self.overall)
            last_avg = avg_from_dict(self.last)
            data = []
            for direction in ['Request', 'Response']:
                data.append({
                    'name': direction,
                    'avg': overall_avg[direction],
                    'last_avg': last_avg[direction]
                })
            table = self.formatter.render_table(data, ['name', 'avg', 'last_avg'])
            for num, direction in enumerate(['Request', 'Response']):
                spark_len = expected_width - self.clean_len(table[0]) - 3
                spark = self.sparkline.get_sparkline(direction, spark_len=spark_len)
                prepared.append(table[num] + ('  ',) + tuple(spark))
        else:
            self.lines.append(('',))
            self.lines.append(('',))
        self.width, self.lines = self.fill_rectangle(prepared)


class AvgTimesBlock(AbstractBlock):
    ''' Average times breakdown '''

    def __init__(self, screen, times_max_spark=120):
        AbstractBlock.__init__(self, screen)
        self.sparkline = Sparkline(times_max_spark)
        self.fraction_keys = [
            'interval_real', 'connect_time', 'send_time', 'latency', 'receive_time']
        self.fraction_names = {
            'interval_real': 'Overall',
            'connect_time':  'Connect',  # noqa: E241
            'send_time':     'Send',  # noqa: E241
            'latency':       'Latency',  # noqa: E241
            'receive_time':  'Receive'}  # noqa: E241
        self.overall = dict([(k, 0) for k in self.fraction_keys])
        self.overall['count'] = 0
        self.last = dict([(k, 0) for k in self.fraction_keys])
        self.last['count'] = 0
        self.title = 'Average Times (all/last), ms:'
        template = {
            'name': {'tpl': '{:>}'},
            'avg': {'tpl': '{:>,.2f}'},
            'last_avg': {'tpl': '{:>,.2f}'}
        }
        delimiters = [': ', ' / ']
        self.formatter = TableFormatter(template, delimiters)

    def add_second(self, data):
        self.last = {}
        self.last['count'] = data["overall"]["interval_real"]["len"]
        self.overall['count'] += self.last['count']
        ts = data["ts"]
        for fraction in self.fraction_keys:
            self.last[fraction] = float(data["overall"][fraction]["total"]) / 1000
            self.overall[fraction] += self.last[fraction]
            self.sparkline.add(ts, fraction, self.last[fraction] / self.last['count'])

    def render(self, expected_width=None):
        prepared = [(self.screen.markup.WHITE, self.title)]
        if self.overall['count']:
            overall_avg = avg_from_dict(self.overall)
            last_avg = avg_from_dict(self.last)
            data = []
            for fraction in self.fraction_keys:
                data.append({
                    'name': self.fraction_names[fraction],
                    'avg': overall_avg[fraction],
                    'last_avg': last_avg[fraction]
                })
            table = self.formatter.render_table(data, ['name', 'avg', 'last_avg'])
            for num, fraction in enumerate(self.fraction_keys):
                spark_len = expected_width - self.clean_len(table[0]) - 3
                spark = self.sparkline.get_sparkline(fraction, spark_len=spark_len)
                prepared.append(table[num] + ('  ',) + tuple(spark))
        else:
            for fraction in self.fraction_keys:
                prepared.append(('-',))
        self.width, self.lines = self.fill_rectangle(prepared)


class CasesBlock(AbstractBlock):
    '''     Cases info    '''

    def __init__(self, screen, cases_sort_by='http_err', cases_max_spark=60, reorder_delay=5, max_case_len=32):
        AbstractBlock.__init__(self, screen)
        self.cumulative_cases = {}
        self.last_cases = {}
        self.title = 'Cumulative Cases Info:'
        self.max_case_len = max_case_len
        self.cases_order = []
        self.reorder_delay = reorder_delay
        self.sparkline = Sparkline(cases_max_spark)
        self.cases_sort_by = cases_sort_by
        self.last_reordered = time.time()
        self.field_order = ['name', 'count', 'percent', 'last', 'net_err', 'http_err', 'avg', 'last_avg']

        template = {
            'name':     {'tpl': '{:>}:',    'header': 'name', 'final': '{{{:}:>{len}}}'},  # noqa: E241
            'count':    {'tpl': '{:>,}',    'header': 'count'},   # noqa: E241
            'last':     {'tpl': '+{:>,}',   'header': 'last'},    # noqa: E241
            'percent':  {'tpl': '{:>.2f}%', 'header': '%'},       # noqa: E241
            'net_err':  {'tpl': '{:>,}',    'header': 'net_e'},   # noqa: E241
            'http_err': {'tpl': '{:>,}',    'header': 'http_e'},  # noqa: E241
            'avg':      {'tpl': '{:>,.1f}', 'header': 'avg ms'},  # noqa: E241
            'last_avg': {'tpl': '{:>,.1f}', 'header': 'last ms'}
        }
        delimiters = [' ']
        self.formatter = TableFormatter(template, delimiters)

    def add_second(self, data):
        def prepare_data(tag_data, display_name):
            count = tag_data["interval_real"]["len"]
            time = tag_data["interval_real"]["total"] / 1000
            net_err, http_err, spark_color = combine_codes(tag_data, self.screen.markup)
            if spark_color == self.screen.markup.GREEN:
                text_color = self.screen.markup.WHITE
            else:
                text_color = spark_color
            return (spark_color, {
                'count': count, 'net_err': net_err, 'http_err': http_err,
                'time': time, 'color': text_color, 'display_name': display_name})

        ts = data["ts"]
        overall = data["overall"]
        self.last_cases = {}
        spark_color, self.last_cases[0] = prepare_data(overall, 'OVERALL')
        self.sparkline.add(ts, 0, self.last_cases[0]['count'], color=spark_color)

        tagged = data["tagged"]
        for tag_name, tag_data in tagged.items():
            # decode symbols to utf-8 in order to support cyrillic symbols in cases
            # name = tag_name.decode('utf-8')
            spark_color, self.last_cases[tag_name] = prepare_data(tag_data, tag_name)
            self.sparkline.add(ts, tag_name, self.last_cases[tag_name]['count'], color=spark_color)
        for name in self.last_cases:
            if name not in self.cumulative_cases:
                self.cumulative_cases[name] = {}
                for k in ['count', 'net_err', 'http_err', 'time', 'display_name']:
                    self.cumulative_cases[name][k] = self.last_cases[name][k]
            else:
                for k in ['count', 'net_err', 'http_err', 'time']:
                    self.cumulative_cases[name][k] += self.last_cases[name][k]

    def __cut_name(self, name):
        if len(name) > self.max_case_len:
            return name[:self.max_case_len - 1] + '…'
        else:
            return name

    def __reorder_cases(self):
        sorted_cases = sorted(self.cumulative_cases.items(),
                              key=lambda item: (-1 * item[1][self.cases_sort_by], str(item[0])))
        new_order = [case for (case, data) in sorted_cases]
        now = time.time()
        if now - self.reorder_delay > self.last_reordered:
            self.cases_order = new_order
            self.last_reordered = now
        else:
            if len(new_order) > len(self.cases_order):
                for case in new_order:
                    if case not in self.cases_order:
                        self.cases_order.append(case)

    def render(self, expected_width=None):
        prepared = [(self.screen.markup.WHITE, self.title)]

        if 0 in self.cumulative_cases:  # 0 used as special name for OVERALL to avoid name collision
            total_count = self.cumulative_cases[0]['count']

            self.__reorder_cases()
            data = []
            for name in self.cases_order:
                case_data = self.cumulative_cases[name]
                if name in self.last_cases:
                    last = self.last_cases[name]
                else:
                    last = {'count': 0, 'net_err': 0, 'http_err': 0, 'time': 0, 'color': '', 'display_name': name}
                data.append({
                    'full_name': name,
                    'name': self.__cut_name(case_data['display_name']),
                    'count': case_data['count'],
                    'percent': 100 * safe_div(case_data['count'], total_count),
                    'last': last['count'],
                    'net_err': case_data['net_err'],
                    'http_err': case_data['http_err'],
                    'avg': safe_div(case_data['time'], case_data['count']),
                    'last_avg': safe_div(last['time'], last['count'])
                })
            table = self.formatter.render_table(data, self.field_order)
            prepared.append(table[0])  # first line is table header
            for num, line in enumerate(data):
                full_name = line['full_name']
                if full_name in self.last_cases:
                    color = self.last_cases[full_name]['color']
                else:
                    color = ''
                spark_len = expected_width - self.clean_len(table[0]) - 3
                spark = self.sparkline.get_sparkline(full_name, spark_len=spark_len)
                prepared.append((color,) + table[num + 1] + ('  ',) + tuple(spark))

        for _ in range(3 - len(self.cumulative_cases)):
            prepared.append(('',))

        self.width, self.lines = self.fill_rectangle(prepared)
