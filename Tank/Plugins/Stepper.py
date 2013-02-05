'''
Tools for preparing phantom input data file
'''

from collections import defaultdict
from progressbar import ProgressBar, Percentage, Bar, ETA
import logging
import operator
import os
import re
import tempfile
import tankcore

# TODO: 3 add stpd file size estimation 
# TODO: 3  chosen cases
def make_load_ammo(uris):
    '''
    Create temp file for uri-format ammo
    '''
    fds, filename = tempfile.mkstemp('.ammo', 'uri_')
    os.close(fds)
    tmp_ammo = open(filename, 'w')
    for line in uris:
        tmp_ammo.write(line + '\n')
    return filename


def get_ammo_type(filename):
    '''
    Detect ammo file format
    '''
    ammo = open(filename, 'r')
    first_line = ammo.readline()
    if re.match("^(\/|\[)", first_line):
        return 'uri'
    elif re.match("^\d", first_line):
        return 'request'
    else:
        raise RuntimeError("Unsupported ammo format in %s" % filename)


def detect_case_file(filename):
    '''
    Detect cases presence
    '''
    ammo = open(filename, 'r')
    first_line = ammo.readline()
    pattern = re.match("^(\d+)\s*\d*\s*(\w*)\s*", first_line)
    if pattern:
        if pattern.group(2):
            return True
    return False


# TODO: 2 eliminate double ammo file pass
def get_ammo_count(filename, stop_count):
    '''
    Long-running damn function
    '''
    logging.info("Getting ammo count from %s ...", filename)

    widgets = [Percentage(), ' ', Bar(), ' ', ETA(), ' ' ]
    pbar = ProgressBar(widgets=widgets, maxval=os.path.getsize(filename)).start()

    ammo_type = get_ammo_type(filename)
    ammo_cnt = 0
    pattern = re.compile("^(GET|POST|PUT|HEAD|OPTIONS|PATCH|DELETE|TRACE|LINK|UNLINK)\s")
    cur_progress = 0
    if ammo_type == 'uri':
        input_ammo = open(filename, 'r')
        for line in input_ammo:
            cur_progress += len(line)
            if re.match("^\/", line):
                ammo_cnt += 1
                pbar.update(cur_progress)
        pbar.finish()
        return ammo_cnt
    elif ammo_type == 'request':
        input_ammo = open(filename, 'r')
        for line in input_ammo:
            cur_progress += len(line)
            if pattern.match(line):
                ammo_cnt += 1
                pbar.update(cur_progress)
            if ammo_cnt == stop_count & stop_count > 0:
                break
        pbar.finish()
        return ammo_cnt


def header_print(values_list):
    '''
    Helper to generate request with headers
    '''
    header = ''
    for (key, val) in values_list.iteritems():
        header += '%s: %s\r\n' % (key, val)
    return header


def get_headers_list(line):
    """
    return a dict of {header: value}, parsed from string
    """

    values_list = defaultdict(str)
    header = re.match("^\[", line)
    if header:
        pattern = re.match("^\[(.+)\]", line)
        if pattern:
            cases = re.split('\]\s*\[', line)
            for case in cases:
                case = re.sub("\[|\]", '', case)
                case_pat = re.match("^\s*(\S+)\s*:\s*(.+?)\s*$", case)
                if case_pat:
                    values_list[case_pat.group(1)] = case_pat.group(2)
    return values_list


def get_common_header(filename):
    '''
    Read headers from ammo file 
    '''
    input_ammo = open(filename, 'r')
    values_list = {}
    for line in input_ammo:
        values_list.update(get_headers_list(line))
    return values_list


def load_const(req, duration):
    '''
    Constant load pattern
    '''
    dur = tankcore.expand_to_seconds(duration)
    steps = []
    steps.append([req, dur])
    loads = '%s,const,%s,%s,(%s,%s)\n' % (dur, req, req, req, duration)
    time = dur * int(req)
    if int(req) == 0:
        time = dur
    return [steps, loads, time]


def load_line(start, end, duration):
    '''
    Linear load pattern
    '''
    dur = tankcore.expand_to_seconds(duration)
    diff_k = float((end - start) / float(dur - 1))
    (cnt, last_x, total) = (1, start, 0)
    loads = '%s,line,%s,%s,(%s,%s,%s)\n' % (
        dur,
        start,
        end,
        start,
        end,
        duration,
        )
    steps = []
    for sec_i in range(1, dur + 1):
        cur_x = int(start + diff_k * sec_i)
        if cur_x == last_x:
            cnt += 1
        else:
            steps.append([last_x, cnt])
            total += cnt * last_x
            (cnt, last_x) = (1, cur_x)
    return [steps, loads, total]


def load_step(start, end, step, duration,):
    '''
    Stepping load pattern
    '''
    dur = tankcore.expand_to_seconds(duration)
    (steps, loads, total) = ([], '', 0)
    if end > start:
        for rps_level in range(start, end + 1, step):
            steps.append([rps_level, dur])
            loads += '%s,step,%s,%s,(%s,%s,%s,%s)\n' % (
                dur,
                rps_level,
                rps_level,
                start,
                end,
                step,
                duration,
                )
            total += rps_level * dur
    else:
        for rps_level in range(start, end - 1, -step):
            steps.append([rps_level, dur])
            loads += '%s,step,%s,%s,(%s,%s,%s,%s)\n' % (
                dur,
                rps_level,
                rps_level,
                start,
                end,
                step,
                duration,
                )
            total += rps_level * dur
    return [steps, loads, total]


def collapse_schedule(schedule):
    '''
    Helper to merge duplicate chunks
    '''
    res = []
    prev_item = []
    rolling_count = 0
    base_time = 0
    for item in schedule:
        if base_time == 0:
            base_time = item[1]
            item[1] = 0
        if prev_item:
            if prev_item[0] == item[0]:
                prev_item[1] += item[1]
                continue
            res += [[prev_item[0] - rolling_count, prev_item[1]]]
            rolling_count = prev_item[0]
        prev_item = item
    if prev_item:
        res += [prev_item]
    return res


def make_steps_element(param_item):
    '''
    Generate schedule element
    '''
    (steps, loadscheme, load_ammo) = ([], '', 0)
    params = []
    params.append(param_item)
    for param_item in params:
        (st, loads, cnt) = ([], '', 0)
        pattern = re.match("^const\s*\(\s*(\d+)\s*,\s*((\d+[hms]?)+)\s*", param_item)
        if pattern:
            (st, loads, cnt) = load_const(int(pattern.group(1)), pattern.group(2))
        else:
            pattern = re.match("^line\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*((\d+[hms]?)+)\s*", param_item)
            if pattern:
                [st, loads, cnt] = load_line(int(pattern.group(1)),
                        int(pattern.group(2)), pattern.group(3))
            else:
                pattern = re.match("^step\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*((\d+[hms]?)+)\s*\)\s*", param_item)
                if pattern:
                    [st, loads, cnt] = load_step(int(pattern.group(1)),
                            int(pattern.group(2)), int(pattern.group(3)),
                            pattern.group(4))
                else:
                    pattern = re.match("^const\s*\(\s*(\d+\/\d+)\s*,\s*((\d+[hms]?)+)\s*", param_item)
                    if pattern:
                        [st, loads, cnt] = constf(pattern.group(1), pattern.group(2))
                    else:
                        raise RuntimeError("[Warning] Wrong load format: '%s'. Aborting." % param_item)
        if loads:
            steps += st
            loadscheme += loads
            load_ammo += cnt
    return (steps, loadscheme, load_ammo)


def expand_load_spec(l):
    '''
    Parse load scpecification
    '''
    (step, loads, cnt, max_val) = ([], '', 0, 0)
    pattern = re.match("^const\s*\(\s*(\d+)\s*,\s*((\d+[hms]?)+)\s*", l)
    if pattern:
        val = int(pattern.group(1))
        (step, loads, cnt) = load_const(val, pattern.group(2))
        if val > max_val:
            max_val = val
    else:
        pattern = \
            re.match("^line\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*((\d+[hms]?)+)\s*", l)
        if pattern:
            val = int(pattern.group(2))
            [step, loads, cnt] = load_line(int(pattern.group(1)), val, pattern.group(3))
            if val > max_val:
                max_val = val
        else:
            pattern = re.match("^step\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*((\d+[hms]?)+)\s*\)\s*", l)
            if pattern:
                val = int(pattern.group(2))
                [step, loads, cnt] = load_step(int(pattern.group(1)), val, int(pattern.group(3)), pattern.group(4))
                if val > max_val:
                    max_val = val
            else:
                pattern = re.match("^const\s*\(\s*(\d+\/\d+)\s*,\s*((\d+[hms]?)+)\s*", l)
                if pattern:
                    [step, loads, cnt] = constf(pattern.group(1), pattern.group(2))
                else:
                    raise RuntimeError("[Warning] Wrong load format: '%s'. Aborting." % l)
    return (step, loads, cnt, max_val)


def make_steps(load_spec):
    '''
    Process schedule
    '''
    (steps, loadscheme, load_ammo) = ([], '', 0)
    for load_item in load_spec:
        if not load_item:
            continue
        (st, loads, cnt, skip) = expand_load_spec(load_item)
        if loads:
            steps += st
            loadscheme += loads
            load_ammo += cnt
    return (steps, loadscheme, load_ammo)


def mark_sec(cnt, dur):
    '''
    second marker?
    '''
    koeff = 1000 / float(cnt)
    times = [0]
    for sec in range(1, cnt * dur):
        times.append(int(sec * koeff))
    return times


def constf(req, duration):
    '''
    Float const load pattern
    '''
    pattern = re.match("(\d+)\/(\d+)", req)
    if pattern:
        (a, b) = (int(pattern.group(1)), int(pattern.group(2)))
        (dur, e) = (tankcore.expand_to_seconds(duration), int(a / b))

        fract = '%.3f' % (float(a) / b)
        loads = '%s,const,%s,%s,(%s,%s)\n' % (dur, fract, fract, req, duration)
        a = a % b
        req = '%s/%s' % (a, b)
        out = []
        tail = dur % b
        for x in range(1, int(dur / b) + 1):
            out += frps(req)
        if tail:
            out += frps_cut(tail, req)
        if e > 0:
            out = frps_expand(out, e)
        return (out, loads, frps_ammo(out))
    else:
        raise RuntimeError("Error in 'const_f' function. rps: %s, duration: %s" % (req, duration))
        


def frps(req):
    '''
    Float const load pattern helper
    '''
    pattern = re.match("(\d+)\/(\d+)", req)
    if pattern:
        c = defaultdict(str)
        num1 = int(pattern.group(1))
        num0 = int(pattern.group(2)) - num1
        if num1 == 0:
            out = []
            for x in range(0, num0):
                out.append([0, 1])
            return out
        if num1 > num0:
            (c['per_chunk'], c['space'], c['first']) = (int(num1
                     / num0), num1 % num0, '1')
            c['chunks'] = int(num0)
            (c['num1'], c['num0']) = (num1, num0)
        else:
            (c['per_chunk'], c['space'], c['first']) = (int(num0
                     / num1), num0 % num1, '0')
            c['chunks'] = int(num1)
            (c['num1'], c['num0']) = (num0, num1)
        return frps_scheme(c)
    else:
        return 0


def frps_print(s, t):
    '''
    Float const load pattern
    '''
    out = []
    for x in range(0, t):
        out.append([s, 1])
    return out


def frps_vv(a):
    '''
    Float const load pattern
    '''
    return (int(a) + 1) % 2


def frps_scheme(c):
    '''
    Float const load pattern
    '''
    out = []
    for x in range(0, c['chunks']):
        out += frps_print(c['first'], c['per_chunk'])
        c['num1'] -= c['per_chunk']
        out += frps_print(frps_vv(c['first']), 1)
        c['num0'] -= 1
    out += frps_print(c['first'], c['num1'])
    out += frps_print(frps_vv(c['first']), c['num0'])
    return out


def frps_cut(c, r):
    '''
    Float const load pattern
    '''
    pattern = re.match("(\d+)\/(\d+)", r)
    if pattern:
        b = int(pattern.group(2))
        if c < b:
            frs = frps(r)
            out = []
            cnt = 0
            for (x, y) in frs:
                cnt += 1
                out.append([x, y])
                if cnt == c:
                    break
            return out
        else:
            raise RuntimeError('Wrong cut: $s for rps %s' % (c, r))
            
    else:
        raise RuntimeError("Wrong rps format in 'frps_cut' function")


def frps_expand(s, e):
    '''
    Float const load pattern
    '''
    out = []
    for (x, y) in s:
        out.append([int(x) + e, y])
    return out


def frps_ammo(s):
    '''
    Float const load pattern
    '''
    cnt = 0
    for (x, y) in s:
        cnt += int(x)
    return cnt


def auto_case(url, pattern):
    '''
    Generate case automatically
    '''
    pattern = pattern.search(url)
    res = ['', '', '']
    if pattern:
        elm = pattern.groups()
        res[0] = 'front_page'
        if elm[1]:
            res[0] = elm[1]
        if elm[1] and elm[3]:
            res[1] = elm[1] + '_' + elm[3]
        if elm[1] and elm[3] and elm[5]:
            res[2] = elm[1] + '_' + elm[3] + '_' + elm[5]
    return res


def get_prepared_case(uri, cases_done, pattern):
    '''
    Get existing cases
    '''
    cases = auto_case(uri, pattern)
    cases.reverse()
    if cases_done:
        for case in cases:
            if cases_done[case]:
                return case
        return 'other'
    else:
        return ''


def get_autocases_tree(filename):
    '''
    Generate case automatically
    '''
    logging.debug("get_autocases_tree")    
    pattern = re.compile('^(GET|POST|PUT|HEAD|OPTIONS|PATCH|DELETE|TRACE|LINK|UNLINK\s+)?\s*\/(.*?)(/(.*?))?(/(.*?))?(\.|/|\?|$|\s)')

    tree = {'other': 'none'}
    (level1, level2, level3) = (defaultdict(int), defaultdict(int), defaultdict(int))
    (total_cnt, line_cnt) = (0, 0)
    input_ammo = open(filename, 'r')
    for line in input_ammo:
        line_cnt += 1
        if re.match("^(\/|GET|POST|PUT|HEAD|OPTIONS|PATCH|DELETE|TRACE|LINK|UNLINK)"
                    , line):
            total_cnt += 1
            cases = auto_case(line, pattern)
            if cases[0]:
                level1[cases[0]] += 1
                tree[cases[0]] = cases[0]
            if cases[1]:
                level2[cases[1]] += 1
                tree[cases[1]] = cases[0]
            if cases[2]:
                level3[cases[2]] += 1
                tree[cases[2]] = cases[1]
    return (level1, level2, level3, tree, total_cnt)


def get_autocases_tree_access(filename):
    '''
    Generate case automatically
    '''
    logging.debug("get_autocases_tree_access")
    pattern = re.compile('(GET|POST|PUT|HEAD|OPTIONS|PATCH|DELETE|TRACE|LINK|UNLINK\s+)\s*\/(.*?)(/(.*?))?(/(.*?))?(\.|/|\?|$|\s)')
    tree = {'other': 'none'}
    (level1, level2, level3) = (defaultdict(int), defaultdict(int),
                                defaultdict(int))
    (total_cnt) = (0)
    input_ammo = open(filename, 'r')
    for line in input_ammo:
        if re.search("(\/|GET|POST|PUT|HEAD|OPTIONS|PATCH|DELETE|TRACE|LINK|UNLINK)"
                     , line):
            total_cnt += 1
            cases = auto_case(line, pattern)
            if cases[0]:
                level1[cases[0]] += 1
                tree[cases[0]] = cases[0]
            if cases[1]:
                level2[cases[1]] += 1
                tree[cases[1]] = cases[0]
            if cases[2]:
                level3[cases[2]] += 1
                tree[cases[2]] = cases[1]
    return (level1, level2, level3, tree, total_cnt)


def make_autocases_top(l1, l2, l3, total_cnt, tree,):
    '''
    Generate case automatically
    '''
    logging.debug("make autocases top")
    (N, alpha) = (9, 1)
    (total_done) = (0)
    output = ''
    cases_done = defaultdict(int)
    sl1 = sorted(l1.iteritems(), key=operator.itemgetter(1), reverse=True)
    sl2 = sorted(l2.iteritems(), key=operator.itemgetter(1), reverse=True)
    sl3 = sorted(l3.iteritems(), key=operator.itemgetter(1), reverse=True)
    n = 0
    output += 'level 1\n'
    for s in sl1:
        t = float(100 * s[1]) / float(total_cnt)
        if t >= alpha and n < N:
            cases_done[s[0]] = s[1]
            total_done += s[1]
            n += 1
            output += '\t%s. [level 1]\t%s\t%.2f%s\n' % (n, s[0], t, '%')
    n = 0
    output += 'level 2:\n'
    for s in sl2:
        t = float(100 * s[1]) / float(total_cnt)
        if t >= alpha and n < N:
            if len(cases_done) < N:
                cases_done[s[0]] = s[1]
                total_done += s[1]
                if cases_done[tree[s[0]]]:
                    cases_done[tree[s[0]]] -= s[1]
                    total_done -= s[1]
                if cases_done[tree[s[0]]] == 0:
                    del cases_done[tree[s[0]]]
                    n -= 1
            n += 1
            output += '\t%s. [level 2]\t%s\t%.2f%s [%s]\n' % (n, s[0],
                    t, '%', tree[s[0]])
    output += 'level 3:\n'
    n = 0
    for s in sl3:
        t = float(100 * s[1]) / float(total_cnt)
        if t >= alpha and n < N:
            if len(cases_done) < N:
                cases_done[s[0]] = s[1]
                total_done += s[1]
                if cases_done[tree[s[0]]]:
                    cases_done[tree[s[0]]] -= s[1]
                    total_done -= s[1]
                if cases_done[tree[s[0]]] == 0:
                    del cases_done[tree[s[0]]]
                    n -= 1
            n += 1
            output += '\t%s. [level 3]\t%s\t%.2f%s [%s]\n' % (n, s[0],
                    t, '%', tree[s[0]])
    n = 0
    if total_done < total_cnt:
        cases_done['other'] = total_cnt - total_done
    csds = sorted(cases_done.iteritems(), key=operator.itemgetter(1),
                  reverse=True)
    output += 'cases done:\n'
    for s in csds:
        n += 1
        t = float(100 * s[1]) / float(total_cnt)
        output += '\t%s. [done]\t%s\t%s\t%.2f%s [%s]\n' % (
            n,
            s[1],
            s[0],
            t,
            '%',
            tree[s[0]],
            )
    return (cases_done, output)

def parse_uri(line):
    '''
    Parse uri... why not use urlparse module?
    '''
    (uri, header_list) = ('', {})
    pattern = re.compile('^(\/\S*?)\s+(\[.+)')
    h = re.match("^\/", line)
    if h:
        m = pattern.match(line)
        if m:
            el = m.groups()
            uri = el[0]
            header_list = get_headers_list(el[1])
        else:
            uri = line
    return (uri, header_list)


def chunk_by_uri(line, http, time, case, common_header, config_header,):
    """Create request for uri and header"""

    header = {}
    header.update(common_header)
    (uri, header_custom) = parse_uri(line)
    if header_custom:
        header.update(header_custom)
    header.update(config_header)
    req = 'GET %s HTTP/%s\r\n' % (uri, http) + header_print(header)\
         + '\r\n'
    chunk = '''%s %s %s
%s
''' % (len(req), time, case, req)
    return chunk

class Stepper:
    '''
    Phantom source data generator
    '''
    HTTP_REQUEST_LINE = '^(GET|POST|PUT|HEAD|OPTIONS|PATCH|DELETE|TRACE|LINK|UNLINK|PROPFIND|PROPPATCH|MKCOL|COPY|MOVE|LOCK|UNLOCK\s+)?\s*\/(.*?)(/(.*?))?(/(.*?))?(\.|/|\?|$|\s)'

    def __init__(self, stpd_filename):
        self.log = logging.getLogger(__name__)
        self.ammofile = None
        self.autocases = 0
        self.tank_type = 1
        self.header_http = '1.0'
        self.rps_schedule = []
        self.instances_schedule = None
        self.headers = []
        self.loop_limit = 0
        self.uris = []
        self.stpd_file = stpd_filename
        # output
        self.loadscheme = None
        self.cases = None
        self.steps = None
        self.loop_count = None
        self.ammo_count = None

    def generate_stpd(self):
        '''
        Main method
        '''
        
        self.log.debug("Generating stpd file: %s", self.stpd_file)
        self.log.debug("Autocases: %s", self.autocases)
        self.log.debug("Ammofile: %s", self.ammofile)
        
        pattern = re.compile(self.HTTP_REQUEST_LINE)

        tank_type = self.tank_type

        (load_steps, load_scheme, load_count) = make_steps(self.rps_schedule)

        instances_schedule_count = 0
        instances_schedule = []
        instances_chunk_cnt = 0
        if self.instances_schedule:
            instances = self.instances_schedule
            sched_parts = instances.split(' ')
            for sched_part in sched_parts:
                if sched_part:
                    [expanded_sched, skip, skip, max_val] = expand_load_spec(sched_part)
                    instances_schedule += expanded_sched
                    if max_val > instances_schedule_count:
                        instances_schedule_count = max_val
            instances_schedule = collapse_schedule(instances_schedule)
    
        ammo_file = self.ammofile
        ammo_type = ''
        ammo_delete = ''

        if tank_type == 1:
            if not ammo_file and self.uris:
                ammo_file = make_load_ammo(self.uris)
                ammo_type = 'uri'
                ammo_delete = ammo_file
            else:
                ammo_type = get_ammo_type(ammo_file)
                if ammo_type == 'unknown':
                    raise RuntimeError('[Error] Unknown type of ammo file'
                            )
                elif ammo_type == 'request':
                    pass
                elif ammo_type == 'uri':
                    pass
        elif tank_type == 2:
            ammo_type = 'request'

        if ammo_type == 'uri':
            header_common = get_common_header(ammo_file)

            header_config = {}
            if self.headers:
                for line in self.headers:
                    header_config.update(get_headers_list(line))

        (cases_done, cases_output, ammo_count) = ({}, '', 0)
        if tank_type == 1:
            if not self.autocases:
                ammo_count = get_ammo_count(ammo_file, load_count)
            else:
                if ammo_type == 'request' and detect_case_file(ammo_file) == True:
                    self.log.debug('Ammo file has cases. Do not create autocases.')
                    ammo_count = get_ammo_count(ammo_file, load_count)
                else:
                    (l1, l2, l3, cases_tree, ammo_count) = get_autocases_tree(ammo_file)
                    if self.autocases:
                        (cases_done, cases_output) = make_autocases_top(l1, l2, l3, ammo_count,
                                cases_tree)

        if self.autocases:
            self.log.debug(cases_output)

        http = self.header_http

        max_progress = 0

        cur_progress = 0

        case = 0

        loop = 0

        if self.loop_limit <= 0:
            if load_count == 0:
                self.log.debug('loop and load2')
                loop = 1
            else:
                loop = -1
        else:
            loop = self.loop_limit

        stop_loop_count = 0

        if loop == 0 and ammo_count < load_count:
            case = 1
            raise RuntimeError("Not enough ammo (%s) in '%s' for load scheme (%s)"
                                % (ammo_count, ammo_file, load_count))

        if loop > 0:
            if load_count == 0:
                case = 2
                self.log.debug('Load scheme is empty')

        if load_count > 0:
            if loop == 0 and load_count <= ammo_count:
                case = 3
            if loop > 0 and load_count <= loop * ammo_count:
                case = 3
            if loop > 0 and loop * ammo_count < load_count:
                self.log.warn('Looped ammo count (%s * %s = %s) is less than load scheme (%s). Using loop count.'\
                     % (loop, ammo_count, loop * ammo_count, load_count))
                stop_loop_count = loop * ammo_count
                case = 3
            if loop == -1:
                case = 3

        self.log.debug('Case: %s. Ammo type: %s' % (case, ammo_type))

        already_cases = defaultdict(int)

        self.log.info("Generating stpd-file...")
        widgets = [Percentage(), ' ', Bar(), ' ', ETA(), ' ' ]
        if ammo_type == 'request':
            if case == 2:
                max_progress = loop * ammo_count
                load_steps = [[0, 0]]
            elif case == 3:
                if stop_loop_count:
                    max_progress = stop_loop_count
                else:
                    max_progress = load_count

            pbar = ProgressBar(widgets=widgets, maxval=max_progress).start()
            base_time = 0

            pattern_uri = re.compile("^(GET|POST|PUT|HEAD|OPTIONS|PATCH|DELETE|TRACE|LINK|UNLINK|PROPFIND|PROPPATCH|MKCOL|COPY|MOVE|LOCK|UNLOCK\s+)?\s*(\/(.*?))($|\s)")

            chunk_case = ''

            input_ammo = open(ammo_file, 'rb')
            stepped_ammo = open(self.stpd_file, 'wb')
            for step in load_steps:
                pbar.update(cur_progress)

                if case == 3:
                    if stop_loop_count > 0 and cur_progress == stop_loop_count:
                        break
                (step_ammo_num, looping) = (0, 1)
                (count, duration) = (step[0], step[1])
                if case == 3:
                    if int(count) == 0:
                        base_time += duration * 1000
                        continue
                    marked = mark_sec(count, duration)
                while looping:
                    chunk_start = input_ammo.readline()

                    if not chunk_start:
                        if not cur_progress:
                            raise RuntimeError("Empty ammo file, can't use it")
                        input_ammo.seek(0)
                        pbar.update(cur_progress)
                        continue

                    m = re.match("^\s*(\d+)\s*\d*\s*(\w*)\s*$",
                                 chunk_start)

                    if m:
                        (chunk_size, chunk_case) = (int(m.group(1)), m.group(2))

                        already_cases[chunk_case] += 1
                        chunk = input_ammo.read(chunk_size)

                        if chunk_size > len(chunk):
                            raise RuntimeError('Unexpected end of ammo file')

                        if chunk:
                            if not chunk_case:
                                request = pattern_uri.match(chunk)
                                if request:
                                    chunk_case = get_prepared_case(request.group(2), cases_done, pattern)
                                else:
                                    chunk_case = 'other'

                            time = 1000

                            if case == 3:
                                time = base_time + marked[step_ammo_num]
                            elif case == 2:
                                if step_ammo_num < instances_schedule_count:
                                    if not instances_chunk_cnt:
                                        [instances_chunk_cnt, instances_chunk_time] = instances_schedule.pop(0)
                                        base_time += instances_chunk_time * 1000
                                    instances_chunk_cnt -= 1
                                    time = base_time
                            else:
                                time = 1000

                            if chunk_case:
                                stepped_ammo.write('%s %s %s\n' % (chunk_size, time, chunk_case))
                            else:
                                stepped_ammo.write('%s %s\n'
                                         % (chunk_size, time))
                            stepped_ammo.write(chunk)
                            stepped_ammo.write('\n')
                            step_ammo_num += 1
                            cur_progress += 1

                        if int(cur_progress) == int(max_progress):
                            looping = 0

                        if case == 3:
                            if stop_loop_count > 0 and cur_progress\
                                 == stop_loop_count:
                                break
                            if step_ammo_num == count * duration:
                                break
                    else:

                        if re.match("^\s*$", chunk_start):
                            pass
                        else:

                            m = re.match("^\s*(\d+)\s*\d*\s*(.*)\s*$",
                                    chunk_start)
                            if m:
                                if m.group(2):
                                    c = re.match("^\w+$", m.group(2))
                                    if not c:
                                        raise RuntimeError("Wrong case format for '%s'" % m.group(2))

                            # TODO: 2 add more info to locate problem chunk
                            raise RuntimeError('Wrong chunk size')

                    if int(cur_progress) == int(max_progress):
                        looping = 0
                        break

                    if case == 3:
                        if stop_loop_count > 0 and cur_progress\
                             == stop_loop_count:
                            break
                        if step_ammo_num == count * duration:
                            break
                        if not step_ammo_num == count * duration:
                            pass
                        if step_ammo_num == load_count:
                            looping = 0
                base_time += duration * 1000

            stepped_ammo.write('0\n')
            pbar.finish()
        elif ammo_type == 'uri':
            if case == 2:
                self.log.debug("Looping '%s' for %s time(s):" % (ammo_file, loop))
                max_progress = loop * ammo_count
                stepped_ammo = open(self.stpd_file, 'w')
                input_ammo = open(ammo_file, 'r')
                for l in range(1, loop + 1):
                    for line in input_ammo:
                        m = re.match("^(http|\/)", line)
                        if m:
                            real_case = \
                                get_prepared_case(line.rstrip(),
                                    cases_done, pattern)
                            chunk = chunk_by_uri(
                                line.rstrip(),
                                http,
                                1000,
                                real_case,
                                header_common,
                                header_config,
                                )
                            stepped_ammo.write(chunk)
                            cur_progress += 1

                    if cur_progress == 0:
                        raise RuntimeError('Eternal loop detected')
                    input_ammo.seek(0)
                stepped_ammo.write('0\n')
            elif case == 3:

                max_progress = load_count
                if stop_loop_count:
                    max_progress = stop_loop_count
                else:
                    max_progress = load_count
                base_time = 0

                stepped_ammo = open(self.stpd_file, 'w')
                input_ammo = open(ammo_file, 'r')
                for step in load_steps:

                    if stop_loop_count > 0 and cur_progress\
                         == stop_loop_count:
                        looping = 0
                        break
                    (step_ammo_num, looping) = (0, 1)
                    (count, duration) = (int(step[0]), int(step[1]))
                    if count == 0:
                        base_time += duration * 1000
                        continue
                    marked = mark_sec(count, duration)

                    while looping:
                        for line in input_ammo:
                            m = re.match("^(http|\/)", line)
                            if m:
                                time = marked[step_ammo_num]
                                real_case = \
                                    get_prepared_case(line.rstrip(),
                                        cases_done, pattern)
                                chunk = chunk_by_uri(
                                    line.rstrip(),
                                    http,
                                    base_time + time,
                                    real_case,
                                    header_common,
                                    header_config,
                                    )
                                stepped_ammo.write(chunk)
                                cur_progress += 1
                                step_ammo_num += 1
                                if stop_loop_count > 0 and cur_progress\
                                     == stop_loop_count:
                                    looping = 0
                                    break
                                if step_ammo_num == count * duration:
                                    looping = 0
                                    break
                        if not step_ammo_num == count * duration:
                            if cur_progress == 0:
                                raise RuntimeError('Eternal loop detected'
                                        )
                            input_ammo.seek(0)
                    base_time += duration * 1000

                stepped_ammo.write('0\n')

        self.ammo_count = str(cur_progress)

        if ammo_count > 0:
            self.loop_count = float(cur_progress) / ammo_count
        else:
            self.loop_count = '0'

        lp_loadscheme = re.sub('\n', ';', load_scheme)
        self.loadscheme = lp_loadscheme

        lp_cases = ''
        if cases_done:
            for s in cases_done:
                if cases_done[s] > 0:
                    lp_cases += "'" + s + "' "
        elif already_cases:
            for s in already_cases:
                if s and already_cases[s] > 0:
                    lp_cases += "'" + s + "' "
                if s == '' and len(already_cases) == 1:
                    lp_cases = "''"
        else:
            lp_cases = "''"
        self.cases = lp_cases

        self.steps = []
        for s in load_steps:
            self.steps += [int(s[0]), int(s[1])]

        if ammo_delete:
            os.unlink(ammo_delete)

        return


