#!/usr/bin/env python
# -*- coding: utf-8 -*-

from collections import defaultdict
import datetime
import operator
import os
import re
import time
import tempfile

# FIXME: remove this hack
import sys
sys.path.append("/usr/lib/python2.5")

from progressbar import Bar
from progressbar import ETA
from progressbar import Percentage
from progressbar import ProgressBar

### Ammo file ###
###
def make_load_ammo(file):
   pattern = re.compile("^\s*(header|uri)\s*=\s*(.+)")
   dt = datetime.datetime.now()
   fd, filename = tempfile.mkstemp('.ammo', 'uri_')
   conf = open(file, "r")
   tmp_ammo = open(filename, "w")
   for line in conf:
      m = pattern.match(line)
      if m:
         el = m.groups()
         tmp_ammo.write(el[1] + "\n")
   return filename

def get_ammo_type(file):
   ammo = open(file, "r")
   first_line = ammo.readline()
   if re.match("^(\/|\[)", first_line):
      return "uri"
   elif re.match("^\d", first_line):
      return "request"
   else:
      return "unknown"

def detect_case_file(file):
   ammo = open(file, "r")
   first_line = ammo.readline()
   m = re.match("^(\d+)\s*\d*\s*(\w*)\s*", first_line)
   if m:
      if m.group(2):
         return True
   return False

def get_ammo_count(file, stop_count):
   ammo_type = get_ammo_type(file)
   ammo_cnt = 0
   pattern = re.compile("^(GET|POST|PUT|HEAD|OPTIONS|PATCH|DELETE|TRACE|LINK|UNLINK)\s")
   if (ammo_type == "uri"):
      input_ammo = open(file, "r")
      for line in input_ammo:
         if re.match("^\/", line):
            ammo_cnt += 1
      return ammo_cnt
   elif (ammo_type == "request"):
      max_progress = file_len(file)
      widgets = ['Checking ammo count: ', Percentage(), ' ', Bar(), ' ', ETA(), ' ' ]
      pbar = ProgressBar(widgets=widgets, maxval=max_progress).start()
      byte_cnt = 0
      input_ammo = open(file, "r")
      for line in input_ammo:
         byte_cnt += len(line)
         pbar.update(byte_cnt)
         if pattern.match(line):
            ammo_cnt += 1
         if ammo_cnt == stop_count & stop_count > 0:
            break
      pbar.finish()
      print
      return ammo_cnt

def get_header(line):
   header = ""
   list = get_headers_list(line)
   for h, v in list.iteritems():
      header += "%s: %s\r\n" % (h, v)
   return header

def header_print(list):
   header = ""
   for h, v in list.iteritems():
      header += "%s: %s\r\n" % (h, v)
   return header

def get_headers_list(line):
   '''return a dict of {header: value}, parsed from string'''
   list = defaultdict(str)
   h = re.match("^\[", line)
   if h:
      m = re.match("^\[(.+)\]", line)
      if m:
         cases = re.split('\]\s*\[', line)
         for case in cases:
            case = re.sub("\[|\]", "", case)
            c = re.match("^\s*(\S+)\s*:\s*(.+?)\s*$", case)
            if c:
               list[c.group(1)] = c.group(2)
   return list 

def get_common_header(file):
   input_ammo = open(file, "r")
   list = {}
   for line in input_ammo:
      list.update(get_headers_list(line))
   return list

### Config file ###
###
class FakeSecHead(object):
   def __init__(self, fp):
      self.fp = fp
      self.sechead = '[DEFAULT]\n'
   def readline(self):
      if self.sechead:
         try:
            return self.sechead
         finally:
            self.sechead = None
      else: return self.fp.readline()

def get_config_multiple(file):
   pattern = re.compile('^\s*(header|load|uri)\s*=\s*(.+)')
   params = defaultdict(list)
   conf = open(file, 'r')
   for line in conf:
      m = pattern.match(line)
      if m:
         el = m.groups()
         if el[0] == 'load':
            for k in  re.findall(r"(line|step|const|const_f)\s*(\(.+?\))\s*", el[1]):
               params[el[0]].append(k[0] + k[1])
         elif el[0] == 'uri':
            params[el[0]].append(el[1].rstrip())
         elif el[0] == 'header':
            params[el[0]].append(el[1].rstrip())
   return params

### Loadscheme ###
###
def load_const(req, duration):
   dur = str2sec(duration)
   steps = []
   steps.append([req, dur])
   ls = "%s,const,%s,%s,(%s,%s)\n" % (dur, req, req, req, duration)
   time = dur * int(req)
   if int(req) == 0:
      time = dur
   return [steps, ls, time]

def load_line(start, end, duration):
   dur = str2sec(duration)
   k = float((end - start) / float(dur - 1))
   cnt, last_x, total = 1, start, 0
   ls = "%s,line,%s,%s,(%s,%s,%s)\n" % (dur, start, end, start, end, duration)
   steps = []
   for i in range(1, dur + 1):
      cur_x = int(start + k * i)
      if (cur_x == last_x):
         cnt += 1
      else:
         steps.append([last_x, cnt])
         total += cnt * last_x
         cnt, last_x = 1, cur_x
   return [steps, ls, total]

def load_step(start, end, step, duration):
   dur = str2sec(duration)
   steps, ls, total = [], "", 0
   if end > start:
      for x in range(start, end + 1, step):
         steps.append([x, dur])
         ls += "%s,step,%s,%s,(%s,%s,%s,%s)\n" % (dur, x, x, start, end, step, duration)
         total += x * dur
   else:
      for x in range(start, end - 1, -step):
         steps.append([x, dur])
         ls += "%s,step,%s,%s,(%s,%s,%s,%s)\n" % (dur, x, x, start, end, step, duration)
         total += x * dur
   return [steps, ls, total]

# for instances
def collapse_schedule(schedule):
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

def make_steps_element(l):
   steps, loadscheme, load_ammo = [], "", 0
   params = []
   params.append(l)
   for l in params:
      st, ls, cnt = [], "", 0
      m = re.match("^const\s*\(\s*(\d+)\s*,\s*((\d+[hms]?)+)\s*", l)
      if m:
         st, ls, cnt = load_const(int(m.group(1)), m.group(2))
      else:
         m = re.match("^line\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*((\d+[hms]?)+)\s*", l)
         if m:
            [st, ls, cnt] = load_line(int(m.group(1)), int(m.group(2)), m.group(3))
         else:
            m = re.match("^step\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*((\d+[hms]?)+)\s*\)\s*", l)
            if m:
               [st, ls, cnt] = load_step(int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4))
            else:
               m = re.match("^const\s*\(\s*(\d+\/\d+)\s*,\s*((\d+[hms]?)+)\s*", l)
               if m:
                  [st, ls, cnt] = constf(m.group(1), m.group(2))
               else:
                  raise RuntimeError("[Warning] Wrong load format: '%s'. Aborting." % (l))
      if ls:
         steps += st
         loadscheme += ls
         load_ammo += cnt
   return (steps, loadscheme, load_ammo)

def expand_load_spec(l):
      st, ls, cnt, max = [], "", 0, 0
      m = re.match("^const\s*\(\s*(\d+)\s*,\s*((\d+[hms]?)+)\s*", l)
      if m:
         val = int(m.group(1))
         st, ls, cnt = load_const(val, m.group(2))
         if val > max:
             max = val
      else:
         m = re.match("^line\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*((\d+[hms]?)+)\s*", l)
         if m:
            val = int(m.group(2))
            [st, ls, cnt] = load_line(int(m.group(1)), val, m.group(3))
            if val > max:
                max = val
         else:
            m = re.match("^step\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*((\d+[hms]?)+)\s*\)\s*", l)
            if m:
               val = int(m.group(2))
               [st, ls, cnt] = load_step(int(m.group(1)), val, int(m.group(3)), m.group(4))
               if val > max:
                   max = val
            else:
               m = re.match("^const\s*\(\s*(\d+\/\d+)\s*,\s*((\d+[hms]?)+)\s*", l)
               if m:
                  [st, ls, cnt] = constf(m.group(1), m.group(2))
               else:
                  raise RuntimeError("[Warning] Wrong load format: '%s'. Aborting." % (l))
      return st, ls, cnt, max

def make_steps(file):
   params = get_config_multiple(file)
   steps, loadscheme, load_ammo = [], "", 0
   for l in params['load']:
      st, ls, cnt, skip = expand_load_spec(l)
      if ls:
         steps += st
         loadscheme += ls
         load_ammo += cnt
   return (steps, loadscheme, load_ammo)

def mark_sec(cnt, dur):
   k = 1000 / float(cnt)
   times = [0]
   for i in range(1, cnt * dur):
      times.append(int(i * k))
   return times

### Fractional rps ###
###

def constf(req, duration):
   m = re.match("(\d+)\/(\d+)", req)
   if m:
      a, b = int(m.group(1)), int(m.group(2))
      dur, e = str2sec(duration), int(a / b)

      fr = "%.3f" % (float(a) / b)
      ls = "%s,const,%s,%s,(%s,%s)\n" % (dur, fr, fr, req, duration)
      a = a % b
      req = "%s/%s" % (a, b)
      out = []
      tail = dur % b
      for x in range(1, int(dur / b) + 1):
         out += frps(req)
      if tail:
         out += frps_cut(tail, req)
      if e > 0:
         out = frps_expand(out, e)
      return (out, ls, frps_ammo(out))
   else :
      print "Error in 'const_f' function. rps: %s, duration: %s" % (req, duration)
      exit(1)

def frps(req):
   m = re.match("(\d+)\/(\d+)", req)
   if m:
      c = defaultdict(str)
      num1 = int(m.group(1))
      num0 = int(m.group(2)) - num1
      if num1 == 0:
         out = []
         for x in range(0, num0):
            out.append([0, 1])
         return out
      if num1 > num0:
         c["per_chunk"], c["space"], c["first"] = int(num1 / num0), num1 % num0, '1'
         c["chunks"] = int(num0)
         c["num1"], c["num0"] = num1, num0
      else :
         c["per_chunk"], c["space"], c["first"] = int(num0 / num1), num0 % num1, '0'
         c["chunks"] = int(num1)
         c["num1"], c["num0"] = num0, num1
      return frps_scheme(c)
   else :
      return 0

def frps_print(s, t):
   out = []
   for x in range(0, t):
      out.append([s, 1])
   return out

def frps_vv(a):
   return (int(a) + 1) % 2

def frps_scheme(c):
   out = []
   for x in range(0, c["chunks"]):
      out += frps_print(c["first"], c["per_chunk"])
      c["num1"] -= c["per_chunk"]
      out += frps_print(frps_vv(c["first"]), 1)
      c["num0"] -= 1
   out += frps_print(c["first"], c["num1"])
   out += frps_print(frps_vv(c["first"]), c["num0"])
   return out

def frps_cut(c, r):
   m = re.match("(\d+)\/(\d+)", r)
   if m:
      a, b = int(m.group(1)), int(m.group(2))
      if c < b:
         frs = frps(r)
         out = []
         cnt = 0
         for x, y in frs:
            cnt += 1
            out.append([x, y])
            if cnt == c:
               break
         return out
      else: 
         print "Wrong cut: $s for rps %s" % (c, r)
         exit(1)
   else :
      print "Wrong rps format in 'frps_cut' function"
      exit(1)

def frps_expand(s, e):
   out = []
   for x, y in s:
      out.append([int(x) + e, y])
   return out

def frps_ammo(s):
   cnt = 0
   for x, y in s:
      cnt += int(x)
   return cnt   

### Autocases ###
###
def auto_case(url, pattern):
   m = pattern.search(url)
   res = ['', '', '']
   if m:
      el = m.groups()
      res[0] = "front_page"
      if el[1]:
         res[0] = el[1]
      if el[1] and el[3]:
         res[1] = el[1] + "_" + el[3]
      if el[1] and el[3] and el[5]:
         res[2] = el[1] + "_" + el[3] + "_" + el[5]
   return res

def get_prepared_case(uri, cases_done, pattern):
   cases = auto_case(uri, pattern)
   cases.reverse()
   if cases_done:
      for case in cases:
         if cases_done[case]:
            return case
      return 'other'
   else:
      return ''

def get_autocases_tree(file):
   ## Pattern for autocase 3rd level
   pattern = re.compile('/(.*?)(/(.*?))?(/(.*?))?(\.|/|\?|$|\s)')
   pattern = re.compile('^(GET|POST|PUT|HEAD|OPTIONS|PATCH|DELETE|TRACE|LINK|UNLINK\s+)?\s*\/(.*?)(/(.*?))?(/(.*?))?(\.|/|\?|$|\s)')
   
   max_progress = file_len(file)
   widgets = ['Creating cases tree: ', Percentage(), ' ', Bar(), ' ', ETA(), ' ' ]
   pbar = ProgressBar(widgets=widgets, maxval=max_progress).start()

   tree = {'other':'none'}
   level1, level2, level3 = defaultdict(int), defaultdict(int), defaultdict(int)
   total_cnt, line_cnt = 0, 0
   input_ammo = open(file, 'r')
   for line in input_ammo:
      line_cnt += 1
      pbar.update(line_cnt)
      if re.match("^(\/|GET|POST|PUT|HEAD|OPTIONS|PATCH|DELETE|TRACE|LINK|UNLINK)", line):
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
   pbar.finish()
   print
   return (level1, level2, level3, tree, total_cnt)

def get_autocases_tree_access(file):
   ## Pattern for autocase 3rd level
   pattern = re.compile('(GET|POST|PUT|HEAD|OPTIONS|PATCH|DELETE|TRACE|LINK|UNLINK\s+)\s*\/(.*?)(/(.*?))?(/(.*?))?(\.|/|\?|$|\s)')
   
   max_progress = file_len(file)
   widgets = ['Creating cases tree: ', Percentage(), ' ', Bar(), ' ', ETA(), ' ' ]
   pbar = ProgressBar(widgets=widgets, maxval=max_progress).start()

   tree = {'other':'none'}
   level1, level2, level3 = defaultdict(int), defaultdict(int), defaultdict(int)
   total_cnt, byte_cnt = 0, 0
   input_ammo = open(file, 'r')
   for line in input_ammo:
      byte_cnt += len(line)
      pbar.update(byte_cnt)
      if re.search("(\/|GET|POST|PUT|HEAD|OPTIONS|PATCH|DELETE|TRACE|LINK|UNLINK)", line):
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
   pbar.finish()
   print
   return (level1, level2, level3, tree, total_cnt)

def accesslog2phout(access_file, phout_file):
   max_progress = file_len(access_file)
   widgets = ['Access log to phout: ', Percentage(), ' ', Bar(), ' ', ETA(), ' ' ]
   pbar = ProgressBar(widgets=widgets, maxval=max_progress).start()

   pattern = re.compile("\[(.+)\s(.+)\].+?\"(.+?)\"\s(\d+)\s.+?(\d+)$")

   access = open(access_file, "r")
   phout = open(phout_file, "w")
   error = open("access.error", "w")

   byte_cnt = 0
   chunk = ""

   for line in access:
      byte_cnt += len(line)
      pbar.update(byte_cnt)
      m = pattern.search(line)
      if m:
         t = str(time.mktime(time.strptime(m.group(1), '%d/%b/%Y:%H:%M:%S'))) + "00"
         s = "%s\t\t%s\t%s\t0\t0\t0\t%s\n" % (t, m.group(5), m.group(5), m.group(4)) 
         phout.write(s)
      else :
         error.write(line)
   phout.write(chunk)
   phout.close()
   error.close()
   access.close()
   pbar.finish()

def make_autocases_top(l1, l2, l3, total_cnt, tree):
   # max cases count & min percentage 
   N, alpha = 9, 1
   total_done, n = 0, 0
   output = ""
   cases_done = defaultdict(int)
   sl1 = sorted(l1.iteritems(), key=operator.itemgetter(1), reverse=True)
   sl2 = sorted(l2.iteritems(), key=operator.itemgetter(1), reverse=True)
   sl3 = sorted(l3.iteritems(), key=operator.itemgetter(1), reverse=True)
   n = 0
   output += "level 1\n"
   for s in sl1:
      t = float(100 * s[1]) / float(total_cnt)
      if t >= alpha and n < N:
         cases_done[s[0]] = s[1]
         total_done += s[1]
         n += 1
         output += "\t%s. [level 1]\t%s\t%.2f%s\n" % (n, s[0], t, '%')
   n = 0
   output += "level 2:\n"
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
         output += "\t%s. [level 2]\t%s\t%.2f%s [%s]\n" % (n, s[0], t, '%', tree[s[0]])
   output += "level 3:\n"
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
         output += "\t%s. [level 3]\t%s\t%.2f%s [%s]\n" % (n, s[0], t, '%', tree[s[0]])
   n = 0
   if total_done < total_cnt:
      cases_done['other'] = total_cnt - total_done
   csds = sorted(cases_done.iteritems(), key=operator.itemgetter(1), reverse=True)
   output += "cases done:\n"
   for s in csds:
      n += 1
      t = float(100 * s[1]) / float(total_cnt)
      output += "\t%s. [done]\t%s\t%s\t%.2f%s [%s]\n" % (n, s[1], s[0], t, '%', tree[s[0]])
   return (cases_done, output)

### Utilities ###
###
def str2sec(st):
   pattern = re.compile('(\d+)(h|m|s|)')
   sec = 0
   m = pattern.match(str(st))
   if m:
      el = m.groups()
      if el[1] == 'h':
         return int(el[0]) * 3600
      elif el[1] == 'm':
         return int(el[0]) * 60
      elif el[1] == 's':
         return int(el[0])
      else:
         return int(el[0])
   return ''

def parse_uri(line):
   uri, header_list = "", {} 
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


def chunk_by_uri(line, http, time, case, common_header, config_header):
   '''Create request for uri and header'''
   chunk = ""
   header = {}
   header.update(common_header)
   (uri, header_custom) = parse_uri(line)
   if header_custom:
      header.update(header_custom)
   header.update(config_header)
   req = "GET %s HTTP/%s\r\n" % (uri, http) + header_print(header) + "\r\n"
   chunk = "%s %s %s\n%s\n" % (len(req), time, case, req)
   return chunk

def file_len(fname):
   return os.path.getsize(fname)

def loop_ammo_file(file, loop, common_header):
   print "1"
   os.system("ls -lah")
   pass
