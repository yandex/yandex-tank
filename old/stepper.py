#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ConfigParser
from collections import defaultdict
from optparse import OptionParser
import os
import re

from progressbar import Bar
from progressbar import ETA
from progressbar import Percentage
from progressbar import ProgressBar
from yandex_load_lunapark import stepper

print
print "==== Stepper ===="

### Command line argumentd
parser = OptionParser()

parser.add_option("-c", "--config", dest="config",
        help="use custom config FILE, insted of load.conf", metavar="FILE", default='load.conf')

parser.add_option("-a", "--ammo", dest="ammo",
        help="FILE with requests", metavar="FILE")

parser.add_option("-s", "--stats", dest="stats", action="store_true",
        help="only ammo stats, no generating")

parser.add_option("-l", "--loadscheme", dest="loadscheme", action="store_true",
        help="only loadscheme creating, no generating")

parser.add_option("--common-header", dest="header", action="store_true",
        help="show common headers from ammo/config")

parser.add_option("--autocases", dest="autocases", action="store_true",
        help="show autocases for given file")

(options, args) = parser.parse_args()

## Pattern for autocase 3rd level
pattern = re.compile('/(.*?)(/(.*?))?(/(.*?))?(\.|/|\?|$|\s)')
pattern = re.compile('^(GET|POST|PUT|HEAD|OPTIONS|PATCH|DELETE|TRACE|LINK|UNLINK|PROPFIND|PROPPATCH|MKCOL|COPY|MOVE|LOCK|UNLOCK\s+)?\s*\/(.*?)(/(.*?))?(/(.*?))?(\.|/|\?|$|\s)')

### Defaults params for config file
default = {}
default["header_http"] = "1.0"
default["autocases"] = "1"
default["tank_type"] = "1"

### Parse config
### using FakeSecHead class for creating fake section [default] in config-file
configuration_file = ConfigParser.SafeConfigParser(default)
configuration_file.optionxform = str
configuration_file.readfp(stepper.FakeSecHead(open(options.config)))

### Tank type: 1 - HTTP requests, 2 - RAW requests (no ammo count and progress bar)
tank_type = configuration_file.getint('DEFAULT', 'tank_type')

### MultiValues parametres
#     load  - list of elements (step, line, const) for load scheme
#     uri   - list of uri for requests
load_multi = stepper.get_config_multiple(options.config)

(load_steps, load_scheme, load_count) = stepper.make_steps(options.config)

# handle instances schedule
try:
    instances_schedule_count = 0
    instances_schedule = []
    instances_chunk_cnt = 0
    instances = configuration_file.get('DEFAULT', 'instances_schedule')
    sched_parts = instances.split(" ")
    for sched_part in sched_parts:
        if sched_part:
            [expanded_sched, skip, skip, max_val] = stepper.expand_load_spec(sched_part)
            instances_schedule += expanded_sched
            if max_val > instances_schedule_count:
                instances_schedule_count = max_val
    instances_schedule = stepper.collapse_schedule(instances_schedule)
except ConfigParser.NoOptionError:
    pass

### Output '--loadscheme' argument
if options.loadscheme:
    print load_scheme
    exit(0)

### Use ammo defined ammo file or creating temp ammo file from config
ammo_file = options.ammo
if not ammo_file:
    ammo_file = configuration_file.get('DEFAULT', 'ammofile')
ammo_type = ""
ammo_delete = ""

if tank_type == 1:
    if load_multi['uri']:
        #print "Creating tmp ammo file"
        ammo_file = stepper.make_load_ammo(options.config)
        ammo_type = "uri"
        ammo_delete = ammo_file
    else:
        # Detect type of ammo file: 'uri', 'request' or 'unknown'
        ammo_type = stepper.get_ammo_type(ammo_file)
        if ammo_type == 'unknown':
            print "[Error] Unknown type of ammo file"
            exit(1)
        elif ammo_type == 'request':
            pass
            #print "[Error] Type of ammo file: 'request'. You have to use stepper.pl instead of stepper.py"
            #exit(1)
        elif ammo_type == 'uri':
            pass
            #print "OK. Type of ammo file: 'uri'"
elif tank_type == 2:
    ammo_type = "request"

### Make common headers from ammo file
if ammo_type == 'uri':
    header_common = stepper.get_common_header(ammo_file)

### Make common headers from config
header_config = {}
if load_multi['header']:
    for line in load_multi['header']:
        header_config.update(stepper.get_headers_list(line))

### Output '--common-header' argument
if options.header:
    if header_common:
        print "==== ammo header begin ===="
        print stepper.header_print(header_common),
        print "===== ammo header end ====="
        print
    if header_config:
        print "==== config header begin ===="
        print stepper.header_print(header_config),
        print "===== config header end ====="
        print

### Autocases (work only for HTTP request - tank_type = 1)
cases_done, cases_output, ammo_count = {}, "", 0
if tank_type == 1:
    if configuration_file.getint('DEFAULT', 'autocases') == 0:
        ammo_count = stepper.get_ammo_count(ammo_file, load_count)
    else:
        if ammo_type == 'request' and stepper.detect_case_file(ammo_file) == True:
            print "Ammo file has cases. Do not create autocases."
            ammo_count = stepper.get_ammo_count(ammo_file, load_count)
        else:
            (l1, l2, l3, cases_tree, ammo_count) = stepper.get_autocases_tree(ammo_file)
            if configuration_file.getint('DEFAULT', 'autocases'):
                (cases_done, cases_output) = stepper.make_autocases_top(l1, l2, l3, ammo_count, cases_tree)

### Output autocases levels for '--autocases' argument
if options.autocases:
    print cases_output

### Output some ammo stats for '--stats' argument
if options.stats:
    print "ammo file: %s" % ammo_file
    print "ammo type: %s" % ammo_type
    print "ammo count: %s" % ammo_count
    print "load count: %s" % load_count
    print
    exit(0)

http = configuration_file.get('DEFAULT', 'header_http')

### max value for ProgressBar
max_progress = 0

### cur progress value
cur_progress = 0

### Case of operation
case = 0

loop = 0

### Case 0. Neither 'load' nor 'loop' presents at 'load.conf'
# loop = 1
#print "load: %s" % load_count
#print load.has_option('default', 'loop')
if not configuration_file.has_option('DEFAULT', 'loop'):
    if load_count == 0:
        print "loop and load2"
        loop = 1
    else:
        loop = -1
else:
    loop = configuration_file.getint('DEFAULT', 'loop')

#print "loop: %s" % loop


base_loop = loop
stop_loop_count = 0

### Case 1. No generating.
# loop = 0 and ammo count not enough for load scheme
if loop == 0 and ammo_count < load_count:
    case = 1
    print "Not enough ammo (%s) in '%s' for load scheme (%s)" % (ammo_count, ammo_file, load_count)
    print
    exit(1)

### Case 2. Only looping.
# loop > 0 and loop*ammo_count < load scheme.
if loop > 0:
    if load_count == 0:
        case = 2
        print "Load scheme is empty"

### Case 3. Load scheme generating.
if load_count > 0:
    if loop == 0 and load_count <= ammo_count:
        case = 3
    if loop > 0 and load_count <= loop * ammo_count:
        case = 3
    if loop > 0 and loop * ammo_count < load_count:
        print "Looped ammo count (%s * %s = %s) is less than load scheme (%s). Using loop count." % (loop, ammo_count, loop * ammo_count, load_count)
        stop_loop_count = loop * ammo_count
        case = 3
    if loop == -1:
        case = 3

print "Case: %s. Ammo type: %s" % (case, ammo_type)

already_cases = defaultdict(int) 

### Ammo Generating
if ammo_type == 'request':
    if case == 2:
        max_progress = loop * ammo_count
        load_steps = [[0, 0]]
    elif case == 3:
        if stop_loop_count:
            max_progress = stop_loop_count
        else:
            max_progress = load_count
        #print "max progress = %s" % max_progress

    base_time = 0

    widgets = ['Ammo Generating: ', Percentage(), ' ', Bar(), ' ', ETA(), ' ' ]
    pbar = ProgressBar(widgets=widgets, maxval=max_progress).start()

    pattern_request = re.compile("^(\d+)\s*\d*\s*(\w*)\s*$")
    pattern_uri = re.compile("^(GET|POST|PUT|HEAD|OPTIONS|PATCH|DELETE|TRACE|LINK|UNLINK|PROPFIND|PROPPATCH|MKCOL|COPY|MOVE|LOCK|UNLOCK\s+)?\s*(\/(.*?))($|\s)")
    pattern_null = re.compile("^0")

    ammo_len, line_num, chunk_begin, ammo = 0, 0, 0, ""
    chunk_len, chunk_case, chunk_num, chunk_line_start = 0, "", 0, 1
    last_added_chunk = ""
   
    input_ammo = open(ammo_file, "rb")
    stepped_ammo = open("ammo.stpd", "wb")
    for step in load_steps:
        if case == 3:
            if stop_loop_count > 0 and cur_progress == stop_loop_count:
                break
        step_ammo_num, looping = 0, 1
        count, duration = step[0], step[1]
        if case == 3:
            if int(count) == 0:
                base_time += duration * 1000
                continue
            marked = stepper.mark_sec(count, duration)
        while looping:
            chunk_start = input_ammo.readline()
#            print chunk_start
            if not chunk_start:
                if not cur_progress:
                    raise RuntimeError("Empty ammo file, can't use it")
                input_ammo.seek(0)
                continue

            m = re.match("^\s*(\d+)\s*\d*\s*(\w*)\s*$", chunk_start)

            # meta information of new chunk - TRUE
            if m:
                chunk_size, chunk_case = int(m.group(1)), m.group(2)
                #print chunk_case
                already_cases[chunk_case] += 1
                chunk = input_ammo.read(chunk_size)

                if chunk_size > len(chunk):
                    print "\n\n[Error] Unexpected end of file"
                    print "Expected chunk size: %s" % chunk_size
                    print "Readed chunk size: %s" % len(chunk)

                    print
                    if chunk:
                        print "Readed chunk:\n----\n%s----\n" % chunk

                    if last_added_chunk:
                        print "Last written chunk:\n----\n%s----\n" % last_added_chunk

                    exit(1)

                if chunk:
                    if not chunk_case:
                        request = pattern_uri.match(chunk)
                        if request:
                            chunk_case = stepper.get_prepared_case(request.group(2), cases_done, pattern)
                        else:
                            chunk_case = 'other'

                    time = 1000
                    #if tank_type == 2:
                        #chunk_case = ''
                    if case == 3:
                        time = base_time + marked[step_ammo_num]
                    elif case == 2:
                        # no load scheme
                        if step_ammo_num < instances_schedule_count:
                            if not instances_chunk_cnt:
                                [instances_chunk_cnt, instances_chunk_time] = instances_schedule.pop(0)
                                base_time += instances_chunk_time * 1000
                            instances_chunk_cnt -= 1
                            time = base_time
                            
                    else:
                        time = 1000
                
                    # write chunk to file    
                    if chunk_case:
                        stepped_ammo.write("%s %s %s\n" % (chunk_size, time, chunk_case))
                    else :
                        stepped_ammo.write("%s %s\n" % (chunk_size, time))
                    stepped_ammo.write(chunk)
                    stepped_ammo.write("\n")
                    step_ammo_num += 1
                    cur_progress += 1
                    last_added_chunk = chunk
                    pbar.update(cur_progress)

                if int(cur_progress) == int(max_progress):
                    looping = 0

                if case == 3:
                    if stop_loop_count > 0 and  cur_progress == stop_loop_count:
                        break
                    if step_ammo_num == count * duration:
                        break
            # meta information of new chunk - FALSE
            else:
                # pass empty strings between requests
                if re.match("^\s*$", chunk_start):
                    pass
                # wrong case format (not \w*)
                else:
                    m = re.match("^\s*(\d+)\s*\d*\s*(.*)\s*$", chunk_start)
                    if m:
                        if m.group(2):
                            c = re.match("^\w+$", m.group(2))
                            if not c:
                                print "Wrong case format for '%s'" % m.group(2)
                                exit(1)
                    print "[Error] Wrong chunk size"
                    print
                    print "Chunk start:\n----\n%s----\n" % chunk_start
                    if chunk:
                        print "Readed chunk:\n----\n%s----\n" % chunk

                    if last_added_chunk:
                        print "Last writed chunk:\n----\n%s----\n" % last_added_chunk

                    exit(1)

            if int(cur_progress) == int(max_progress):
                looping = 0
                break

            if case == 3:
                if stop_loop_count > 0 and cur_progress == stop_loop_count:
                    break
                if step_ammo_num == count * duration:
                    break
                if not step_ammo_num == count * duration:
                    pass
                if step_ammo_num == load_count:
                    looping = 0
        base_time += duration * 1000

    stepped_ammo.write("0\n")
    pbar.finish()

elif (ammo_type == "uri"):
    # Only looping.
    if case == 2:
        print "Looping '%s' for %s time(s):" % (ammo_file, loop)
        print
        max_progress = loop * ammo_count  
        widgets = ['Ammo Generating: ', Percentage(), ' ', Bar(), ' ', ETA(), ' ' ]
        pbar = ProgressBar(widgets=widgets, maxval=max_progress).start()
   
        stepped_ammo = open("ammo.stpd", "w")
        input_ammo = open(ammo_file, "r")
        for l in range(1, loop + 1):
            for line in input_ammo:
                m = re.match("^(http|\/)", line)
                if m:
                    real_case = stepper.get_prepared_case(line.rstrip(), cases_done, pattern)
                    chunk = stepper.chunk_by_uri(line.rstrip(), http, 1000, real_case, header_common, header_config)
                    stepped_ammo.write(chunk)
                    cur_progress += 1
                    pbar.update(cur_progress)
                    #sleep(1)
            if cur_progress == 0:
                raise RuntimeError("Eternal loop detected")
            input_ammo.seek(0)
        stepped_ammo.write("0\n")
        pbar.finish()
        print
    # Steps generating
    elif case == 3:
        max_progress = load_count  
        if stop_loop_count:
            max_progress = stop_loop_count
        else:
            max_progress = load_count
        base_time = 0

        widgets = ['Ammo Generating: ', Percentage(), ' ', Bar(), ' ', ETA(), ' ' ]
        pbar = ProgressBar(widgets=widgets, maxval=max_progress).start()
   
        stepped_ammo = open("ammo.stpd", "w")
        input_ammo = open(ammo_file, "r")
        for step in load_steps:
#            print step
            if stop_loop_count > 0 and cur_progress == stop_loop_count:
                looping = 0
                break
            step_ammo_num, looping = 0, 1
            count, duration = int(step[0]), int(step[1])
            if count == 0:
                base_time += duration * 1000
                continue
            marked = stepper.mark_sec(count, duration)
#            print "marked: %s" % marked
            while looping:
                for line in input_ammo:
                    m = re.match("^(http|\/)", line)
                    if m:
                        time = marked[step_ammo_num]
                        real_case = stepper.get_prepared_case(line.rstrip(), cases_done, pattern)
                        chunk = stepper.chunk_by_uri(line.rstrip(), http, base_time + time, real_case, header_common, header_config)
                        stepped_ammo.write(chunk)
                        cur_progress += 1
                        step_ammo_num += 1
                        pbar.update(cur_progress)
                        if stop_loop_count > 0 and cur_progress == stop_loop_count:
                            looping = 0
                            break
                        if step_ammo_num == count * duration:
                            looping = 0
                            break
                if not step_ammo_num == count * duration:
                    if cur_progress == 0:
                        raise RuntimeError("Eternal loop detected")
                    input_ammo.seek(0)
            base_time += duration * 1000

        stepped_ammo.write("0\n")
        pbar.finish()
        print

### Save shared data to 'lp.conf' for using by 'preproc', 'fantom' and '-s' argument
if not os.path.exists("lp.conf"):
    lp_conf = open("lp.conf", "w")
    lp_conf.close()

lp = ConfigParser.SafeConfigParser(default)
lp.readfp(stepper.FakeSecHead(open("lp.conf")))

lp.set('DEFAULT', 'ammo_count', str(cur_progress))

if ammo_count > 0:
    lp.set('DEFAULT', 'loop_count', "%.2f" % (float(cur_progress) / ammo_count)) 
else:
    lp.set('DEFAULT', 'loop_count', "0") 

if instances_schedule_count:
    lp.set('DEFAULT', 'instances_schedule', "%s" % instances) 
    
lp_loadscheme = re.sub("\n", ";", load_scheme);
lp.set('DEFAULT', 'loadscheme', lp_loadscheme)

lp_cases = ''
if cases_done:
    for s in cases_done:
        if cases_done[s] > 0:
            lp_cases += "'" + s + "' "
elif already_cases :
    for s in already_cases:
        if s and already_cases[s] > 0:
            lp_cases += "'" + s + "' "
        if s == "" and len(already_cases) == 1:
            lp_cases = "''"
else:
    lp_cases = "''"
lp.set('DEFAULT', 'cases', lp_cases)

lp_steps = ''
for s in load_steps:
    lp_steps += "(%s;%s) " % (s[0], s[1])
lp.set('DEFAULT', 'steps', lp_steps)

configfile = open('lp.conf', 'wb')
lp.write(configfile)

### Delete tmp load ammo file
if ammo_delete:
    os.unlink(ammo_delete)

exit(0)
