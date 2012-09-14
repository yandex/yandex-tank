#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import re
import time
import datetime
import os
import ConfigParser
import logging
import json
import urllib2

from collections import defaultdict
from optparse import OptionParser
from subprocess import Popen, PIPE

from yandex_load_lunapark import stepper, status 

if os.getenv("DEBUG"):
    log_level = logging.DEBUG
else:
    log_level = logging.INFO
logging.basicConfig(filename='fantom-debug.log', filemode='w', level=log_level, format="%(asctime)-15s %(message)s")

### Default percentiles and timings for display
times_percent = {100: 1, 99: 1, 98: 1, 95: 1, 90: 1, 85: 1, 80: 1, 75: 1, 50: 1, 25: 1}
times_time = {}

class Widget(object):
    def __init__(self, **kwargs):
        opt = {'x': 0, 'y': 0, 'w': 0, 'h': 0, 'id': '', 'text': '',
               'color': '', 'rel_name': '', 'rel_y': 0, 'error': 0}
        opt.update(kwargs)
        for key, value in opt.iteritems():
            setattr(self, key, value)
    def render(self, matrix, maxw, maxh):
        for y in xrange(0, self.h):
            if (self.y + y) < len(matrix):
                for x in xrange(0, self.w):
                    if (self.x + x) < len(matrix[self.y + y]):
                        if (self.x + x < maxw) & (self.y + y < maxh):
                            matrix[self.y + y][self.x + x] = ' '
        text = str(self.text)
        try:
            if re.search("\n", text):
                y = self.y
                set = text.split("\n")
                for s in set:
                    if y < len(matrix):
                        for x in xrange(0, min(self.w, len(s))):
                            if (self.x + x < maxw) & (y < maxh):
                                matrix[y][self.x + x] = s[x]
                        y += 1
                        if y == self.y + self.h:
                            break
            else:
                for x in xrange(0, min(self.w, len(text))):
                    if (self.x + x < maxw) & (self.y + y < maxh):
                        matrix[self.y][self.x + x] = text[x]
        except TypeError:
            if not self.error:
                out = "text:\n%s\n" % text
                out += "\n\nid: %s" % self.id
                self.error = 1

class Screen(object):
    def __init__(self, width, height):
        self.widgets = {}
        self.matrix = []
        self.width = width
        self.height = height
        for y in xrange(0, height):
            self.matrix.append([]) 
            for x in xrange(0, width):
                self.matrix[y].append(' ')

    def register_widget(self, id, x, y, w, h,
                        text='', color='', rel_name='', rel_y=0):
        self.widgets[id] = Widget(**{
            'x': x, 'y': y, 'w': w, 'h': h, 'id': id, 'text': text,
            'color': color, 'rel_name': rel_name, 'rel_y': rel_y
        })

    def set_param(self, id, param, value):
        setattr(self.widgets[id], param, value)
    def set_text(self, id, text):
        self.widgets[id].text = text
    def set_height(self, id, h):
        self.widgets[id].h = h
    def set_color(self, id, color):
        self.widgets[id].color = color
    def set_y(self, id, y):
        self.widgets[id].y = y
    def delete_widget(self, id):
        if self.widgets[id]:
            del self.widgets[id]
    def render_color(self):
        os.system("clear")
        color_matrix = defaultdict(str)
        for id in self.widgets:
            text = str(self.widgets[id].text)
            if self.widgets[id].rel_name:
                rel_name = str(self.widgets[id].rel_name)
                self.widgets[id].y = self.widgets[rel_name].y + self.widgets[rel_name].h + self.widgets[id].rel_y
            self.widgets[id].render(self.matrix, self.width, self.height)
            if self.widgets[id].color:
                x, y, w, h, color = self.widgets[id].x, self.widgets[id].y, self.widgets[id].w, self.widgets[id].h, self.widgets[id].color
                if color == 'on_red':
                    pass
                if len(text) > 0:
                    color_matrix['%s;%s' % (x, y)] = color
                    color_matrix['%s;%s' % (x + w - 1, y)] = 'reset'
                    for t in range(0, h):
                        color_matrix['%s;%s' % (x, y + t)] = color
                        color_matrix['%s;%s' % (x + w - 1, y + t)] = 'reset'

        y = 0
        for line in self.matrix:
            x = 0
            for el in line:
                out = el 
                if color_matrix['%s;%s' % (x, y)]:
                    if color_matrix['%s;%s' % (x, y)] == 'gray':
                        pass
                        #out = '\033[30;3m%s' % el
                    elif color_matrix['%s;%s' % (x, y)] == 'red':
                        out = '\033[31;3m%s' % el
                    elif color_matrix['%s;%s' % (x, y)] == 'on_red':
                        out = '\033[41;3m%s' % el
                    elif color_matrix['%s;%s' % (x, y)] == 'on_yellow':
                        out = '\033[43;3m%s' % el
                    elif color_matrix['%s;%s' % (x, y)] == 'on_blue':
                        out = '\033[44;3m%s' % el
                    elif color_matrix['%s;%s' % (x, y)] == 'reset':
                        out = '%s\033[0m' % el
                sys.stdout.write(out)
                x += 1
            sys.stdout.write("\n") 
            y += 1
        self.render_empty()
    def render_empty(self):
        for y in xrange(0, self.height):
            for x in xrange(0, self.width):
                self.matrix[y][x] = ' '

    def render(self):
        mt = []
        for id in self.widgets:
            self.widgets[id].render(self.matrix, self.width, self.height)
            if id == 'sum_req_title':
                print "Aga"
                self.widgets[id].render(mt)
                print mt 
            print line

def getconfig(filename):
    config = defaultdict(str)

    f = open(filename, 'r')
    for line in f:
        if re.match("^\s*#", line):
            continue
        m = re.match("^\s*(.+?)\s*=\s*(.+?)(#|$)", line)
        if m:
            if not config[m.group(1)]:
                config[m.group(1)] = []
            config[m.group(1)].append(m.group(2))
    f.close
    return config

def config_sanitize(config):
    stop = {'net': defaultdict(list), 'http': defaultdict(list), 'time': defaultdict(list)}
    for k, v in config.iteritems():
        if k == 'autostop':
            for el in v:
                m = re.match("(net|http)\s*\(\s*(\d+|\dxx|xx)\s*,\s*(\d+%?)\s*,\s*(\d+)\s*\)", el)
                if m:
                    stop[m.group(1)][m.group(2)].append({'dur': m.group(4), 'fails': 0, 'law': m.group(3)})
                else:
                    m = re.match("(time)\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*", el)
                    if m:
                        stop[m.group(1)][m.group(2)].append({'dur': m.group(3), 'fails': 0, 'law': m.group(2)})
    return stop

def getTerminalSize():
    # Default value, in case of failure 'stty size'
    rows, cols = 45, 150
   
    out = Popen(["stty", "size"], stdout=PIPE).communicate()[0]
    m = re.match("(\d+)\s+(\d+)", out)
    if m:
        if (int(m.group(1)) > 0) & (int(m.group(2)) > 0) :
            rows, cols = int(m.group(1)), int(m.group(2))
    return [int(rows), int(cols)]

def create_empty_grid(w, h):
    s = Screen(w, h)

    ### First Line
    s.register_widget('job_title', 3, 1, 5, 1, 'Job :', 'gray')
    s.register_widget('job_num', 9, 1, 5, 1, '')
    s.register_widget('job_name', 15, 1, 15, 1, '', 'gray')
    s.register_widget('duration_title', 35, 1, 9, 1, 'Duration:', 'gray')
    s.register_widget('duration', 45, 1, 9, 1, '')
    s.register_widget('step_begin', 56, 1, 6, 1, '[step: ', 'gray')
    s.register_widget('step', 63, 1, 8, 1, '')
    s.register_widget('step_end', 71, 1, 2, 1, ']', 'gray')

    ### Second Line
    s.register_widget('date_title', 3, 2, 5, 1, 'Date:', 'gray')
    s.register_widget('date', 9, 2, 21, 1, '')
    s.register_widget('complete_title', 35, 2, 9, 1, 'Complete:', 'gray')
    s.register_widget('complete_bar', 45, 2, 37, 1, '', '')
    s.register_widget('complete', 83, 2, 7, 1, '', '')
    s.register_widget('remain_title', 94, 2, 10, 1, 'Remaining:', 'gray')
    s.register_widget('remain', 105, 2, 9, 1, '', '')
    s.register_widget('load_title', 119, 1, 20, 1, 'Load Configuration:', 'gray')

    ### Ruler
    l = 110
    s.register_widget('title_ruler', 3, 3, l, 1, '~' * l)
   
    ### Requests review
    # 1st column
    s.register_widget('req_title', 3, 6, 11, 1, 'ReqPS     : ', 'gray')
    s.register_widget('req', 15, 6, 6, 1, '')
    s.register_widget('avg_req_title', 3, 8, 11, 1, 'AvgReqSize: ', 'gray')
    s.register_widget('avg_req', 15, 8, 12, 1, '')
    s.register_widget('sum_req_title', 3, 9, 11, 1, 'SumReqSize: ', 'gray')
    s.register_widget('sum_req', 15, 9, 12, 1, '')

    # 2nd column
    s.register_widget('resp_title', 25, 6, 12, 1, 'ResPS      : ', 'gray')
    s.register_widget('resp', 38, 6, 9, 1, '')
    s.register_widget('avg_answ_time_title', 25, 7, 12, 1, 'AvgAnswTime: ', 'gray')
    s.register_widget('avg_answ_time', 38, 7, 9, 1, '')
    s.register_widget('avg_answ_size_title', 25, 8, 12, 1, 'AvgAnswSize: ', 'gray')
    s.register_widget('avg_answ_size', 38, 8, 9, 1, '')
    s.register_widget('sum_answ_size_title', 25, 9, 12, 1, 'SumAnswSize: ', 'gray')
    s.register_widget('sum_answ_size', 38, 9, 9, 1, '')

    # 3rd column
    s.register_widget('for_step_title', 47, 5, 9, 1, 'for step ', 'gray')
    s.register_widget('for_step_resp', 47, 6, 9, 1, '')
    s.register_widget('for_step_time', 47, 7, 9, 1, '')
    s.register_widget('for_step_avg', 47, 8, 9, 1, '')
    s.register_widget('for_step_sum', 47, 9, 9, 1, '')

    # 4th column (raw data)
    s.register_widget('times_raw_title', 58, 5, 25, 1, '.  Times for step: (raw)', 'gray')
    s.register_widget('times_raw', 59, 6, 55, int(h - 10), '')
   
    # Vertical Ruler
#   for x in range(5, 13):
#      pass
#      s.register_widget('ruler_58_%s' % x, 58, x, 1, 1, '.', 'gray')
    for x in range(1, 33):
        pass
        s.register_widget('ruler_112_%s' % x, 116, x, 1, 1, '.', 'gray')
    ### Network codes

    ### Bottom
    s.register_widget('selfload_title', 3, h - 3, 10, 1, 'Self-load: ', 'gray')
    s.register_widget('selfload', 14, h - 3, 6, 1, ' ', 'gray')
    s.register_widget('timelag_title', 22, h - 3, 9, 1, 'Time-lag: ', 'gray')
    s.register_widget('timelag', 32, h - 3, 10, 1, '', 'gray')

    return s

def int2minsec(dur):
    h, m, s = 0, 0, 0
    h = dur / 3600
    m = (dur - h * 3600) / 60
    s = dur % 60
    return '%02d:%02d:%02d' % (h, m, s)

def bytes_convert(bytes):
    pre = ['b', 'Kb', 'Mb', 'Gb', 'Tb', 'Pb', 'Eb']
    last = '%s%s' % (bytes, pre[0])
    bytes = float(bytes)
    for x in range(1, len(pre)):
        base = 1024 ** x
        if bytes >= float(base):
            last = '%.1f%s' % (bytes / base, pre[x])
        else:
            break
    return last

def get_proc_stat():
    f = open("/proc/stat", "r")
    cpu = f.readline().split()
    return cpu[1:5]

def get_cpu_usage(list):
    stat = get_proc_stat()
    total, idle = 0, 0
    idle = int(stat[3]) - int(list[3])
    for i in range(len(stat)):
        total += int(stat[i]) - int(list[i])
    percent = 0
    if total:
        percent = 100 * (total - idle) / total
    return [percent, stat]

def get_disk_usage():
    f = os.popen("df -hlx fuse")
    data = (0, 0, 0)
    for l in f:
        m = re.search("([\d\.,]+\w)\s+([\d\.,]+\w)\s+([\d\.,]+\w)\s+([\d\.,]+)%\s+\/$", l)
        if m:
            data = (m.group(2), m.group(1), int(100.0 - float(m.group(4))))
    return data

def get_mem_usage():
    f = os.popen("free")
    for l in f:
        m = re.search("Mem:\s+(\d+)\s+(\d+)\s+(\d+)", l)
        if m:
            percent = int(100 * float(m.group(3)) / float(m.group(1)))
            mem_all = bytes_convert(int(m.group(1)) * 1024)
            mem = bytes_convert(int(m.group(2)) * 1024)
            return (mem, mem_all, '%s%%' % percent)

def get_api_addr():
    logging.info("Getting config info")
    dbconf = ConfigParser.SafeConfigParser()
    dbconf.optionxform = str
    try:
        dbconf.read("/etc/lunapark/db.conf")
        if not dbconf.get('DEFAULT', "http_base"):
            logging.warn("No KSHM API setting, no db connect")
            return None
    except Exception, e:
            logging.exception(e)
            logging.warn("No KSHM API setting, no db connect")
            return None
        
    addr = dbconf.get('DEFAULT', "http_base")
    logging.debug("API address: " + addr)
    return addr

def get_sla_by_task(component):
    if not component or component == '0':
        logging.debug("Skip SLA get")
        return []
    
    logging.info("Requesting SLA for component %s", component)
    addr = API_ADDR + 'api/regress/' + component + '/slalist.json'
    logging.debug('HTTP Request: %s' % (addr))
    req = urllib2.Request(addr)
    resp = urllib2.urlopen(req).read()
    logging.debug('HTTP Response: %s' % resp)
    response = json.loads(resp)
    
    sla = []
    for sla_item in response:
        sla.append((sla_item['prcnt'], sla_item['time']))

    return sla

def list_selector(case, list, list_case):
    if case:
        return  list_case[case].iteritems()
    else:
        return  list.iteritems()
    
def send_data_to_storage(api_data):
    ''' Handle HTTP data send'''
    if not api_data:
        logging.debug("Nothing to send to server")
        return        
    send_data = json.dumps(api_data)
    addr = API_ADDR + 'api/job/' + jobno + '/push_data.json'
    logging.debug('HTTP Request: %s\tlength: %s' % (addr, len(send_data)))
    logging.debug('HTTP Request data: %s' % send_data.strip())
    req = urllib2.Request(addr, send_data)
    resp = urllib2.urlopen(req).read()
    logging.debug('HTTP Response: %s' % resp)
    response = json.loads(resp)
    return response[0]['success']

### Command line argumentd
logging.info('Start')
parser = OptionParser()
parser.add_option("-c", "--config", dest="config",
        help="use custom config FILE, instead of load.conf", metavar="FILE", default='load.conf')

parser.add_option("-p", "--phantom-start", dest="start",
        help="phantom start time (for calculating time lag)", type="int", default=0)

(options, args) = parser.parse_args()
API_ADDR = get_api_addr()

# initital /proc/stat
stat = get_proc_stat()

config = getconfig(options.config)
stop = config_sanitize(config)
stop_data = {'net': defaultdict(int), 'http': defaultdict(int)}

r, c = getTerminalSize()

s = create_empty_grid(c, r - 1)

rgx_overall = re.compile('^overall=1')
rgx_end = re.compile('^===')
rgx_time = re.compile('^time=(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})')
rgx_self = re.compile('^selfload=(.+)%$')
rgx_req = re.compile('^reqps=(-?\d+)')
rgx_case = re.compile('^case=(.*)$')
rgx_resp = re.compile('^answ_time=(\d+)-(\d+):(\d+)')
rgx_http = re.compile('^HTTPcode=(\d+):(\d+)')
rgx_netw = re.compile('^netwcode=(\d+):(\d+)')
rgx_answ = re.compile('^(input|output|tasks|interval_real_expect)=(\d+)')
rgx_prcn = re.compile('^(.+?)_q(\d+)=(\d+)')
rgx_expect = re.compile('^(connect_time|latency|receive_time|send_time)_expect=(\d+)')
rgx_disp = re.compile('^(.+?_dispersion)=(\d+)')

test_duration = 0

# config parse
logging.info('Parse config, prepare scheme')
(steps, loadscheme, load_ammo) = stepper.make_steps(options.config)

for c in steps:
    test_duration += c[1]

load = ConfigParser.RawConfigParser()
load.optionxform = str
load.readfp(stepper.FakeSecHead(open("lp.conf")))

# cases list
now_case = defaultdict(int)
now_case['http'] = defaultdict(int)
now_case['net'] = defaultdict(int)
now_case['answ'] = defaultdict(int)
for el in re.findall("'.+?'", load.get('DEFAULT', 'cases')):
    case = el[1:-1]
    now_case['http'][case] = defaultdict(int)
    now_case['net'][case] = defaultdict(int)
    now_case['answ'][case] = defaultdict(int)

# update procentiles by task components
if API_ADDR:
    try:
        sla = get_sla_by_task(load.get('DEFAULT', 'component'))
        for k, v in sla:
            if k:
                times_percent.update({int(float(k)): 1})
            if v:
                times_time.update({int(float(v)): 1})
    except Exception, e:
        logging.warning("Error getting SLA data: %s", e);
        
# loadscheme
load_multi = stepper.get_config_multiple(options.config)
iter = 1
scheme_count = [0]
for l in load_multi['load']:
    s.register_widget('load_%s' % iter, 119, 1 + iter, 30, 1, '%s. %s' % (iter, l), 'gray')
    (steps, loadscheme, load_ammo) = stepper.make_steps_element(l)
    scheme_count.append(load_ammo + scheme_count[iter - 1])
    iter += 1
    if iter > 20:
        s.register_widget('load_%s' % iter, 119, 1 + iter, 30, 1, '... (%s more)' % (len(load_multi['load']) - 20), 'gray')
        iter += 1
        break

# layout[job info]
jobno = load.get('DEFAULT', 'jobno')
s.set_param('job_num', 'text', load.get('DEFAULT', 'jobno'))

if load.has_option('DEFAULT', 'task'):
    s.set_param('job_name', 'text', load.get('DEFAULT', 'task'))

# layout[ammo] 
s.register_widget('ammo_title', 119, iter + 2, 30, 1, 'Ammo:', 'gray')

onoff = {'0': 'off', '1': 'on'}
ammo_iter, ammo_out = 0, ''

ammo_path = load.get('DEFAULT', 'ammo_path')
ammo_count = load.getint('DEFAULT', 'ammo_count')

m = re.match("^(.+)\/(.+)", ammo_path)
if m.group(2):
    ammo_out += m.group(2) + '\n'
    ammo_iter += 1

ammo_out += 'a/cases :  %s\n' % onoff[load.get('DEFAULT', "autocases")]
ammo_out += 'count   :  %s\n' % ammo_count

ammo_iter += 3
iter += 3
s.register_widget('ammo', 119, iter, 30, ammo_iter, ammo_out, 'gray')
iter += ammo_iter

cases_out, cases_iter = '', 0

if cases_out:
    s.register_widget('cases_title', 119, iter - 1, 9, 1, 'cases   :', 'gray')
    s.register_widget('cases', 130, iter - 1, 20, cases_iter, cases_out, '')
    iter += cases_iter
   
# layout[target & host]
s.register_widget('target_title', 119, iter, 35, 1, 'Target:', 'gray')
target, port = load.get('DEFAULT', 'target_host'), load.get('DEFAULT', 'target_port')
s.register_widget('target', 119, iter + 1, 35, 1, '%s:%s' % (target, port), 'gray')
iter += 3

# layout[tank]
tank = load.get('DEFAULT', 'tank')
tank_short = tank
m = re.match('(.+)\.tanks\.yandex\.net', tank)
if m:
    tank_short = m.group(1)
s.register_widget('tank_title', 119, iter, 30, 1, 'Tank %s:' % tank_short, 'gray')
s.register_widget('tank_cpu_title', 119, iter + 1, 5, 1, 'CPU: ', 'gray')
s.register_widget('tank_cpu', 124, iter + 1, 30, 1, '', '')
s.register_widget('tank_mem_title', 119, iter + 2, 5, 1, 'MEM: ', 'gray')
s.register_widget('tank_mem', 124, iter + 2, 30, 1, '', '')
s.register_widget('tank_disk_title', 119, iter + 3, 5, 1, 'HDD: ', 'gray')
s.register_widget('tank_disk', 124, iter + 3, 30, 1, '', '')

# layout[person]
person = load.get('DEFAULT', 'person')
s.register_widget('person_first', 112 - len(person), 1, 2, 1, ' %s' % person[0], 'red')
s.register_widget('person_name', 114 - len(person), 1, len(person), 1, '%s' % person[1:], '')

overall = 0
ammo = 0
remain, duration, ammo_duration = 0, 0, 0 
time_progress, ammo_progress = 0, 0
last_req = 0

### Data for output
selfload, test_date, test_cur_date, case, req = 0, '', '' , '', '0'
expect, disper, input, output = 0, 0, 0, 0
total_ammo = 0
q = defaultdict(int)

### Timings (rgx_expect)
timing = defaultdict(float)
 
### Detailed timing
detailed = 'interval_real'

now = defaultdict(int)
now['net'] = defaultdict(int)
now['http'] = defaultdict(int)
now['answ'] = defaultdict(int)

cases_resps = defaultdict(int)
step = defaultdict(int)
full = defaultdict(str)
prcn = defaultdict(int)
times = defaultdict(int)
periods = defaultdict(int)

flags = defaultdict(int)

test_start_date = datetime.datetime.fromtimestamp(options.start)
logging.debug('Test start date: %s', test_start_date)
test_cur_date = test_start_date

step = defaultdict(int)
step['duration'] = 1
step['count'] = 0
step['http'] = defaultdict(int)
step['netw'] = defaultdict(int)
times = defaultdict(int)

#print "test duration: %s" % test_duration
line_count = 0

# calculate max hanging time: job timeout from config + 30 sec
last_activity_tm = time.clock()
hangup_time = load.get('DEFAULT', 'timeout')
if hangup_time.endswith('s'):
    hangup_time = float(hangup_time.replace('s', ''))
else:
    hangup_time = float(hangup_time) / 1000.0
hangup_time += 30.0

logging.debug('Open preprocess log')
prepr = open(sys.argv[1], 'r')
while 1:
    logging.debug('Readline from preprocess start')
    line = prepr.readline()

    if not line:
        logging.debug('Line skipped: [' + line + ']')
        if (time.clock() - last_activity_tm > hangup_time):
            print "Hanging is detected"
            break

        time.sleep(0.1)
        continue
    
    #logging.debug('Line accepted: '+line)
    last_activity_tm = time.clock()

    line_count += 1

    if rgx_overall.match(line):
        overall = 1
    # time
    m = rgx_time.match(line)
    if m:
        test_date = "%s-%s-%s %s:%s:%s" % m.groups()
        test_cur_date = datetime.datetime.strptime(test_date, '%Y-%m-%d %H:%M:%S')
        logging.debug('Test cur date: %s', test_cur_date)
        if overall:
            duration += 1

    # reqps
    m = rgx_req.match(line)
    if m:
        req = int(m.group(1))
        if overall:
            if test_duration > 0:
                if req != last_req and duration < test_duration:
                    last_req = req
                    step = defaultdict(int)
                    step['duration'] = 1
                    step['count'] = 0
                    step['http'] = defaultdict(int)
                    step['netw'] = defaultdict(int)
                    times = defaultdict(int)
                else:
                    step['duration'] += 1

    # response time
    #logging.debug('Parse response time')
    m = rgx_resp.match(line)
    if m:
        el = m.groups()
        c = int(m.group(3))
        cases_resps[case] += c
        now['answ'][el[0]] = [el[1], el[2]]
        if case:
            now_case['answ'][case][el[0]] = [el[1], el[2]]
        if overall:
            times[int(el[0])] += int(el[2])
            periods[int(el[0])] = int(el[1])
            ammo_duration += c
            ammo_progress = 100 * float(ammo_duration) / ammo_count
            now['count'] += c
            step['count'] += c
            total_ammo += c

    # case
    #logging.debug('Parse case')
    m = rgx_case.match(line)
    if m:
        if overall:
            case = ''
        else:
            case = m.group(1)

    # http code
    #logging.debug('Parse http code')
    m = rgx_http.match(line)
    if m:
        code, cnt = m.group(1), int(m.group(2))
        now['http'][int(code)] = cnt
        if case:
            now_case['http'][case][int(code)] = cnt
        if overall:
            step['http'][code] += cnt
            stop_data['http'][code] += cnt
            for c in stop['http']:
                m = re.match("^(\d)xx", c)
                if m:
                    if int(code) >= int(m.group(1)) * 100 and int(code) < ((int(m.group(1)) + 1) * 100):
                        stop_data['http']["%sxx" % m.group(1)] += cnt  

    # net code
    #logging.debug('Parse net code')
    m = rgx_netw.match(line)
    if m:
        code, cnt = m.group(1), int(m.group(2))
        now['net'][int(code)] = cnt
        if case:
            now_case['net'][case][int(code)] = cnt
        if overall:
            step['netw'][code] += cnt
            stop_data['net'][code] += cnt
            for c in stop['net']:
                m = re.match("^(\d)xx", c)
                if m:
                    if int(code) >= int(m.group(1)) * 100 and int(code) < ((int(m.group(1)) + 1) * 100):
                        stop_data['net']["%sxx" % m.group(1)] += cnt  
                else:
                    m = re.match("^xx", c)
                    if m:
                        if int(code) > 0:
                            stop_data['net']["xx"] += cnt  
                  
    # answ size
    #logging.debug('Parse answer size')
    m = rgx_answ.match(line)
    if m:
        if overall:
            k, v = m.group(1), int(m.group(2))
            now[k] = v
            step[k] += v
        else:
            k, v = m.group(1), int(m.group(2))
            now[k] = v

    # timings
    #logging.debug('Parse timings')
    m = rgx_expect.match(line)
    if m:
        k, v = m.group(1), int(m.group(2))
        timing[k] = "%.3f" % (float(v) / 1000)

    # detailed dispersion
    #logging.debug('Parse detailed dispersion')
    m = rgx_disp.match(line)
    if m:
        if overall:
            k, v = m.group(1), int(m.group(2))
            now['dispersion'] = v
            step['dispersion'] += v
        else:
            k, v = m.group(1), int(m.group(2))
            now['dispersion'] = v

    # percentiles
    #logging.debug('Parse percentiles')
    m = rgx_prcn.match(line)
    if m:
        detailed = m.group(1)
        if overall:
            q[int(m.group(2))] = float(int(m.group(3))) / 1000
            prcn[int(m.group(2))] = int(m.group(3))
        else:
            q[int(m.group(2))] = float(int(m.group(3))) / 1000

    # selfload
    #logging.debug('Parse selfload')
    m = rgx_self.match(line)
    if m:
        selfload = m.group(1)

    # end chunk and output
    #logging.debug('Parse end chunk')
    if rgx_end.match(line):
        expect = float(now["interval_real_expect"]) / 1000
        expect_step = float(now["interval_real_expect"]) / 1000
        disper = float(now["dispersion"]) / 1000
        input = int(now["input"])
        output = int(now["output"])

        #print q

        if API_ADDR:            
            ### Upload data
            api_data = {
                    'overall': int(overall),
                    'case': case,
                    'net_codes': [],
                    'http_codes': [],
                    'time_intervals': [],
              }

            api_data['trail'] = {
                    'time': str(test_cur_date),
                    'reqps': int(req),
                    'resps': int(cases_resps[case]),
                    'expect': float(expect),
                    'disper': float(disper),
                    'self_load': float(selfload),
                    'input': int(input),
                    'output': int(output),
                    'q50': float(q[50]),
                    'q75': float(q[75]),
                    'q80': float(q[80]),
                    'q85': float(q[85]),
                    'q90': float(q[90]),
                    'q95': float(q[95]),
                    'q98': float(q[98]),
                    'q99': float(q[99]),
                    'q100': float(q[100]),
                    'connect_time': float(timing['connect_time']),
                    'send_time': float(timing['send_time']),
                    'latency': float(timing['latency']),
                    'receive_time': float(timing['receive_time']),
                    'threads': int(now['tasks']),
                }

            cases_resps[case] = 0

            # trail_net and run_trail_net
            for code, cnt in list_selector(case, now['net'], now_case['net']):
                api_data['net_codes'].append({'code': int(code), 'count': int(cnt)})      

            # trail_resp and run_trail_resp
            for code, cnt in list_selector(case, now['http'], now_case['http']):
                api_data['http_codes'].append({'code':int(code), 'count': int(cnt)})      

            # response time
            for t1, t2 in list_selector(case, now['answ'], now_case['answ']):
                api_data['time_intervals'].append({'from':int(t1), 'to': int(t2[0]), 'count': int(t2[1])})       

            can_send = 0
            try:
                can_send = send_data_to_storage(api_data)
            except Exception, e:
                logging.error("Error sending data to server: %s", e);
                logging.info("Retry in 30 seconds")
                print ("Error sending data to server, retry in 30 seconds")
                time.sleep(30)
                try:
                    can_send = send_data_to_storage(api_data)
                except Exception, e:
                    logging.error("Error sending data to server: %s", e);
                    exit(1)

            if not can_send:
                logging.warn('Seems the job was closed remotely')
                exit(1)
            api_data = None


        if overall:
            ### progress bar (time)
            if test_duration:
                time_progress = min(100 * float(duration) / test_duration, 100.0)
                remain = max(test_duration - duration, 0)
            if time_progress == 100.0:
                s.delete_widget('complete_bar')
                s.set_text('complete', '')
                s.register_widget('complete_bar', 45, 2, 7, 1, '', '')
                s.set_text('complete_bar', '%.1f%%' % time_progress)
            else:
                s.set_text('complete_bar', '[' + '=' * int(35 * time_progress / 100) + ' ' * (35 - int(35 * time_progress / 100)) + ']')
                s.set_text('complete', '%.1f%%' % time_progress)
            s.set_text('remain', int2minsec(remain))
            s.set_text('date', test_date)
            s.set_text('timelag', int2minsec((datetime.datetime.now() - test_cur_date).seconds))

            ### progress bar (ammo)
            if time_progress == 100.0 or not steps:
                s.register_widget('complete_ammo', 54, 2, 5, 1, 'Ammo:', 'gray')
                s.register_widget('complete_ammo_bar', 60, 2, 22, 1, '', 'red')
                s.set_text('complete_ammo_bar', '[' + '=' * int(20 * ammo_progress / 100) + ' ' * (20 - int(20 * ammo_progress / 100)) + ']')
                s.set_text('complete', '%.1f%%' % ammo_progress)
            for l in range(len(scheme_count)):
                if ammo_duration < scheme_count[l]:
                    s.set_color('load_%s' % l, '')
                    if l > 1:
                        s.set_color('load_%s' % (l - 1), 'gray')
                    break

            s.set_text('req', str(req))
            s.set_text("selfload", selfload)

            s.set_text('duration', int2minsec(duration))
            s.set_text('step', int2minsec(step['duration']))
            s.set_text('resp', str(now["count"]))

            if now["count"]:
                s.set_text('avg_req', bytes_convert(int(now["output"]) / now["count"]))
                s.set_text('avg_answ_size', bytes_convert(int(now["input"]) / now["count"]))
            else:
                s.set_text('avg_answ_size', bytes_convert(0))
                s.set_text('avg_req', bytes_convert(0))

            s.set_text('sum_req', bytes_convert(now["output"]))
         
            if step['duration']:
                s.set_text('for_step_resp', '%.1f' % (float(step['count']) / step['duration']))
                s.set_text('for_step_time', '%.1f' % (float(step['interval_real_expect']) / (1000 * step['duration'])))
            else:
                s.set_text('for_step_resp', '%.1f' % (float(0)))
                s.set_text('for_step_time', '%.1f' % (float(0)))
            
            if step["count"]:
                s.set_text('for_step_avg', bytes_convert(int(float(step["input"]) / step["count"])))
            else:
                s.set_text('for_step_avg', bytes_convert(0))
            
            s.set_text('sum_answ_size', bytes_convert(now["input"]))
            s.set_text('avg_answ_time', '%.1f' % expect)
            s.set_text('for_step_sum', bytes_convert(step["input"]))
         

            s.register_widget('network_title', 3, 12, 30, 1, 'Network for step: ', 'gray')
            # network codes
            s.register_widget('netcode_err', 35, 12, 2, 1, '', 'on_red')
         
            s.register_widget('http_title', 3, 13, 20, 1, 'HTTP for step: ', 'gray', 'network', 1)

            netw_out = ''
            cnt = 0
            for code, count in sorted(step['netw'].items()):
                if step['count']:
                    netw_out += "%7d %6.2f%%: %s %s\n" % (count, float(100 * count) / step['count'], code, status.net[int(code)])
                    if count > step['count']:
                        print "count: %s, step cnt: %s" % (count, step['count'])
                        print "line count: " , line_count
                        logging.debug("Exiting because count > step['count']")
                        exit(1)
                else:
                    netw_out += "%7d %6.2f%%: %s %s\n" % (
                        count, float(0), code, status.net[int(code)])
                if int(code) > 0 or flags['1xx']:
                    s.set_text('netcode_err', ' ')
                    flags['1xx'] = 1
                cnt += 1
            s.register_widget('network', 1, 13, 40, cnt, '')
            s.set_text('network', netw_out)
         
            # http codes
            s.register_widget('http_3xx', 35, 12, 2, 1, '', 'on_blue', 'network', 1)
            s.register_widget('http_4xx', 38, 12, 2, 1, '', 'on_yellow', 'network', 1)
            s.register_widget('http_5xx', 41, 12, 2, 1, '', 'on_red', 'network', 1)

            http_out = ''
            cnt = 0
            for code, count in sorted(step['http'].items()):
                http_dsc = ''
                if int(code) in status.http:
                    http_dsc = status.http[int(code)]
                if step['count']:
                    http_out += "%7d %6.2f%%: %s %s\n" % (
                        count, float(100 * count) / step['count'], code, http_dsc)
                else:
                    http_out += "%7d %6.2f%%: %s %s\n" % (
                        count, float(0), code, http_dsc)
                if re.match("^3\d+", code) or flags["3xx"]:
                    s.set_text("http_3xx", ' ')
                    flags["3xx"] = 1
                if re.match("^4\d+", code) or flags["4xx"]:
                    s.set_text("http_4xx", ' ')
                    flags["4xx"] = 1
                if re.match("^5\d+", code) or flags["5xx"]:
                    s.set_text("http_5xx", ' ')
                    flags["5xx"] = 1
                cnt += 1
            #print flags
            s.register_widget('http', 1, 15, 40, cnt, '', '', 'network', 2)
            s.set_text('http', http_out)
         
            raw_out = ''
            per_count = step['count']
            per_count = 0
            str_count = 0
            percent = defaultdict(int)
            pertimes = defaultdict(int)
            raw_total_count = 0
            for t in sorted(times.iterkeys()):
                str_count += 1
                per_count += times[t]
                raw_total_count += times[t]
                if step['count']:
                    p1 = '%.2f' % (float(100 * times[t]) / step['count'])
                    p2 = '%.2f' % (float(100 * per_count) / step['count'])
                    percent[float(100 * per_count) / step['count']] = periods[t]
                    pertimes[periods[t]] = float(100 * per_count) / step['count']
                    p1 = ' ' * (7 - len(p1)) + p1
                    p2 = ' ' * (7 - len(p2)) + p2
                else:
                    #pass
                    p1 = '%.2f' % (float(0))
                    p2 = '%.2f' % (float(0))
                    percent[0] = periods[t]
                    pertimes[periods[t]] = float(0)
                raw_out = '%8d %s%%: %03d  --  %03d     %s%%  <  %03d\n' % (times[t], p1, t, periods[t], p2, periods[t]) + raw_out 

            raw_out += '\n%8d  %s%%: total\n' % (raw_total_count, "100.00")
  
            percent_list = times_percent.keys()
            percent_list.sort()
            time_list = times_time.keys()
            time_list.sort()
         
            delta = len(percent_list)
            if len(time_list) > len(percent_list):
                delta = len(time_list)

            tmp_y = 20 
            s.register_widget('time_step_title_prc', 3, tmp_y, 20, 1, 'Times for sec: (%)', 'gray', 'network', cnt + 4)
            s.register_widget('time_step_prc', 3, tmp_y + 1, 20, delta, '', '', 'network', cnt + 5)
            prcn = defaultdict(int)

            last = 0
            for key in percent_list:
                for k in sorted(percent.iterkeys()):
                    if k < key:
                        continue
                    else:
                        prcn[key] = percent[k]
                        break
            prcn_percent_out = ''
            for key in sorted(prcn.iterkeys(), reverse=True):
                prcn_percent_out += '%3d%% <%5dms\n' % (key, prcn[key])
            s.set_text('time_step_prc', prcn_percent_out)
            s.set_text('times_raw', raw_out)
        
            if len(time_list):
                s.register_widget('time_step_title_ms', 31, tmp_y, 20, 1, 'Times for sec: (ms)', 'gray', 'network', cnt + 4)
                s.register_widget('time_step_ms', 31, tmp_y + 1, 20, delta, '', '', 'network', cnt + 5)
                prcn = defaultdict(int)
                for key in time_list:
                    for k in sorted(pertimes.iterkeys()):
                        if k < key:
                            continue
                        else:
                            prcn[key] = pertimes[k]
                            break
                    if not prcn[key]:
                        prcn[key] = 100.0
                prcn_time_out = ''
                for key in sorted(prcn.iterkeys(), reverse=True):
                    prcn_time_out += '%3d%% <%5dms\n' % (prcn[key], key)
                s.set_text('time_step_ms', prcn_time_out)

            ### Layout[Bottom]
         
            # Autostop processing
            logging.debug('Determine autostop')
            autostop_count = 0
            s.register_widget('autostop', 3, tmp_y, 45, 1, 'test', 'red', 'network', cnt + delta + 6)
            autostop_out = ''

            # time
            #print "Autostop"
            for k, v in stop["time"].iteritems():
                #print v
                for el in v:
                    # check
                    if expect >= float(el["law"]):
                        el["fails"] += 1
                    else:
                        el["fails"] = 0

                    # print
                    if el['fails'] > 0:
                        autostop_count += 1
                        autostop_out += 'AUTOSTOP by TIME (reason: %sms for %ss)\nnow: %ss\n\n' % (el["law"], el['dur'], el['fails'])

                    # exit
                    if el["fails"] > int(el["dur"]):
                        print "fantom: exit by autostop (time)"
                        logging.debug('Exit by autostop time')
                        exit(2)

            # http & net codes
            #print "codes"
            for type in ('http', 'net'):
                #print "type: %s" % type
                for k, v in stop[type].iteritems():
                    for el in v:
                        # percentage condition (law)
                        m = re.match("^(\d+)%", el['law'])
                        if m:
                            if now['count'] > 0 and 100 * float(stop_data[type][k]) / now['count'] >= float(m.group(1)):
                                el['fails'] += 1
                            else:
                                el['fails'] = 0
                            #print "key: %s\t data: %s" % (k, el)
#                        print "\t",
#                        print 100*float(stop_data[type][k])/now['count']
                        else:
                            m = re.match("^(\d+)", el['law'])
                            if m:
                                if float(stop_data[type][k]) >= float(m.group(1)):
                                    el['fails'] += 1
                                else:
                                    el['fails'] = 0
                        #print "key: %s\t data: %s" % (k, el)

                        # print
                        if el['fails'] > 0:
                            autostop_count += 1
                            autostop_out += 'AUTOSTOP by %s (reason: %s [>%s] for %ss)\nnow: %ss\n\n' % (type.upper(), k, el['law'], el['dur'], el['fails'])

                        # exit
                        if el['fails'] > int(el['dur']):
                            print "fantom: exit by autostop (%s)" % type
                            if type == 'http':
                                logging.debug('Exit by autostop http')
                                exit(3)
                            elif type == 'net':
                                logging.debug('Exit by autostop net')
                                exit(4)

            #print "Autostop count: %s" % (autostop_count) 
            #print autostop_out

            s.set_height('autostop', autostop_count * 3 - 1)
            s.set_text('autostop', autostop_out)
         
            # tank systems update
            [percent, stat] = get_cpu_usage(stat)
            s.set_text('tank_cpu', '%s%%' % percent)
            s.set_text('tank_mem', '%s / %s (%s free)' % get_mem_usage())
            s.set_text('tank_disk', '%s / %s (%s%% free)' % get_disk_usage())


            ### Initializing for new second
            ###
            overall = 0

            # data for whole second (overall = 1)
            now = defaultdict(int)
            now['net'] = defaultdict(int)
            now['http'] = defaultdict(int)
            now['answ'] = defaultdict(int)

            # data for each case in second (overall = 0)
            now_case = defaultdict(int)
            now_case['http'] = defaultdict(int)
            now_case['net'] = defaultdict(int)
            now_case['answ'] = defaultdict(int)
            for el in re.findall("'.+?'", load.get('DEFAULT', 'cases')):
                case = el[1:-1]
                now_case['http'][case] = defaultdict(int)
                now_case['net'][case] = defaultdict(int)
                now_case['answ'][case] = defaultdict(int)
            
            # data for autostop
            stop_data = {'net': defaultdict(int), 'http': defaultdict(int)}

            # percentiles
            now['prcn'] = defaultdict(int)

            ### Output rendered widgets
            logging.debug('Render screen')
            s.render_color()

            ### Exit when all requests have been processed
            if total_ammo >= ammo_count:
                logging.debug('Ammo done')
                print "All ammo done"
                break

logging.info('End')
