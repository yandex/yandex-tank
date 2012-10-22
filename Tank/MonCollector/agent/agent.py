#! /usr/bin/python
from optparse import OptionParser
from subprocess import Popen, PIPE
import ConfigParser
import base64
import commands
import logging
import os
import re
import socket
import sys
import time

class CpuLa(object):

    def columns(self,):
        return ['System_la1', 'System_la5', 'System_la15']

    def check(self,):
        loadavg_str = open('/proc/loadavg', 'r').readline().strip()
        return map(str, loadavg_str.split()[:3])

class CpuStat(object):
    ''' read /proc/stat and calculate amount of time
        the CPU has spent performing different kinds of work.
    '''
    def __init__(self,):
        # cpu data
        self.check_prev = None
        self.check_last = None
        
        # csw, int data
        self.current = None
        self.last = None

    def columns(self,):
        columns = ['System_csw', 'System_int',
                   'CPU_user', 'CPU_nice', 'CPU_system', 'CPU_idle', 'CPU_iowait',
                   'CPU_irq', 'CPU_softirq', 'System_numproc', 'System_numthreads']
        return columns 

    def check(self,):

        # Empty symbol for no data
        EMPTY = ''

        # resulting data array
        result = []

        # Context switches and interrups. Check.
        try:
            output = Popen('cat /proc/stat | grep -E "^(ctxt|intr|cpu) "',
                            shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        except Exception:
            result.append([EMPTY] * 9)
        else: 
            err = output.stderr.read()
            if err:
                result.extend([EMPTY] * 9)
            else:
                info = output.stdout.read()

                # CPU. Fetch data
                cpus = info.split("\n")[0].split()[1:8]
                fetch_cpu = lambda: map(float, cpus)

                # Context switches and interrupts. Fetch data
                data = []
                for line in info.split("\n")[1:3]:
                    if line:
                        data.append(line.split()[1])
                fetch_data = lambda: map(float, data)

                # Context switches and interrups. Analyze.
                if self.last:
                    self.current = fetch_data()
                    delta = []
                    cnt = 0
                    for el in self.current:
                        delta.append(self.current[cnt] - self.last[cnt])
                        cnt += 1
                    self.last = self.current
                    result.extend(map(str, delta))
                else:
                    self.last = fetch_data()
                    result.extend([EMPTY] * 2)
#                logger.debug("Result: %s" % result)

                # CPU. analyze.
#                logger.debug("CPU start.")
                if self.check_prev is not None:
                    self.check_last = fetch_cpu()
                    delta = []
                    cnt = 0
                    sum_val = 0
                    for v in self.check_last:
                        column_delta = self.check_last[cnt] - self.check_prev[cnt]
                        sum_val += column_delta
                        delta.append(column_delta)
                        cnt += 1

                    cnt = 0
                    for column in self.check_last:
                        result.append(str((delta[cnt] / sum_val) * 100))
                        cnt += 1
                    self.check_prev = self.check_last
                else:
                    self.check_prev = fetch_cpu()
                    result.extend([EMPTY] * 7)
#                logger.debug("Result: %s" % result)
                    
        # Numproc, numthreads 
        # FIXME: 1 remove this expensive operations!!!
        command = ['ps axf | wc -l', 'ps -eLf | wc -l']
        for cmd in command:
            try:
                output = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
            except Exception:
                result.append(EMPTY)
            else:
                err = output.stderr.read()
                if err:
                    result.append(EMPTY)
                else:
                    result.append(str(int(output.stdout.read().strip()) - 1))
        return result


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

class Custom(object):

    def __init__(self, **kwargs):
        for key, value in kwargs.iteritems():
            setattr(self, key, value)
            self.diff_values = {}

    def columns(self,):
        cols = []
        for el in self.tail:
            cols.append("Custom:" + el)
        for el in self.call:
            cols.append("Custom:" + el)
        return cols

    def check(self,):
        res = []
        for el in self.tail:
            cmd = base64.b64decode(el.split(':')[1])
            output = Popen(['tail', '-n', '1', cmd], stdout=PIPE).communicate()[0]
            res.append(self.diff_value(output.strip()))
        for el in self.call:
            cmd = base64.b64decode(el.split(':')[1])
            output = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE).stdout.read()
            res.append(self.diff_value(el, output.strip()))
        return res

    def diff_value(self, config_line, value):
        if not is_number(value):
            #logging.warning("Non-numeric result string, defaulting value to 0: %s", value)
            value = 0
        params = config_line.split(':')
        if len(params) > 2 and int(params[2]):
            if config_line in self.diff_values:
                diffvalue = float(value) - self.diff_values[config_line]
            else:
                diffvalue = 0
            self.diff_values[config_line] = float(value)
            value = diffvalue
        return str(value)


class Disk(object):
    def __init__(self):
        self.read = 0
        self.write = 0

    def columns(self,):
        return ['Disk_read', 'Disk_write']

    def check(self,):
        # cluster size
        size = 512

        # Current data
        read, write = 0, 0
    
        try:
            stat = Popen(["cat /proc/diskstats | awk '{print $3, $7, $11}'"],
                            stdout=PIPE, stderr=PIPE, shell=True)
        except Exception, e:
            logging.error("%s: %s" % (e.__class__, str(e)))
            result = ['', '']
        else: 
            err = stat.stderr.read()
            if err:
                logging.error(err.rstrip())
                result = ['', '']
            else:
                for el in stat.stdout:
                    data = el.split()
                    read += int(data[1])
                    try:
                        write += int(data[2])
                    except:
                        pass
                if self.read:
                    result = [str(size * (read - self.read)), str(size * (write - self.write))]
                else:
                    result = ['', '']
        self.read, self.write = read, write
        return result



class Io(object):
    ''' Get no virtual block device names and count theys r/rw sectors '''
    def __init__(self,):
        self.check_prev = None
        self.check_last = None

    def columns(self,):
        columns = []
        self.block_devs = commands.getoutput('ls -l /sys/block/ | grep -v "virtual" | awk \'{print $8}\' | grep -v "^$"').split('\n')
        for dev_name in self.block_devs:
            columns.extend([dev_name + '-rsec', dev_name + '-wsec'])
        return columns

    def fetch(self,):
        tmp_data = []
        result = {}
        for dev_name in self.block_devs:
            tmp_data = map(int, commands.getoutput('cat /proc/diskstats | grep " ' + dev_name + ' "').split()[5:])
            result[dev_name] = tmp_data[0], tmp_data[4]
        return result

    def check(self,):
        if self.check_prev is not None:
            self.check_last = self.fetch()
            delta = []
            for dev_name in self.block_devs:
                delta.extend([str(self.check_last[dev_name][0] - self.check_prev[dev_name][0]),
                                str(self.check_last[dev_name][1] - self.check_prev[dev_name][1])])
            self.check_prev = self.check_last
            return delta
        else:
            # first check
            self.check_prev = self.fetch()
            return ['0', '0', '0', '0', ]



EMPTY = ''
class Mem(object):
    """
    Memory statistics
    """

    def __init__(self):
        self.name = 'advanced memory usage'
        self.nick = ('used', 'buff', 'cach', 'free', 'dirty')
        self.vars = ('MemUsed', 'Buffers', 'Cached', 'MemFree', 'Dirty', 'MemTotal')
#        self.open('/proc/meminfo')

    def columns(self):
        columns = ['Memory_total', 'Memory_used', 'Memory_free', 'Memory_shared', 'Memory_buff', 'Memory_cached']
        logging.info("Start. Columns: %s" % columns)
        return columns

    def check(self):
        result = []
        try:
            output = Popen('cat /proc/meminfo', shell=True, stdout=PIPE, stderr=PIPE)
        except Exception, e:
            logging.error("%s: %s" % (e.__class__, str(e)))
            result.append([EMPTY] * 9)
        else:
            err = output.stderr.read()
            if err:
                result.extend([EMPTY] * 9)
                logging.error(err.rstrip())
            else:
                info = output.stdout.read()
                
                data = {}
                for name in self.vars:
                    data[name] = 0
                
                for l in info.splitlines():
                    if len(l) < 2: continue
                    [name, raw_value] = l.split(':')
#                    print "name: %s " % name
                    if name in self.vars:
#                       print name, raw_value
                        data.update({name: long(raw_value.split()[0]) / 1024.0})
#                print data
                data['MemUsed'] = data['MemTotal'] - data['MemFree'] - data['Buffers'] - data['Cached']
            result = [data['MemTotal'], data['MemUsed'], data['MemFree'], 0, data['Buffers'], data['Cached']]
            return map(str, result)


class NetRetrans(object):
    ''' read netstat output and
    calculate tcp segment retransmition derivative '''
    def __init__(self,):
        self.retr_second = None
        self.retr_first = None

    def columns(self,):
        return ['Net_retransmit', ]

    def check(self,):
        self.fetch = lambda: int(commands.getoutput('netstat -s | grep "segments retransmited" | awk \'{print $1}\''))
        if self.retr_second is not None:
            self.retr_first = self.fetch()
            self.delta = []
            self.delta.append(str(self.retr_first - self.retr_second))
            self.retr_second = self.retr_first
            return self.delta
        else:
            # first check
            self.retr_second = self.fetch()
            return ['0', ]





class NetTcp(object):
    ''' Read ss util output and count TCP socket's number grouped by state '''

    def __init__(self,):
        self.fields = ['Net_closewait', 'Net_estab', 'Net_listen', 'Net_timewait', ]
        self.keys = ['CLOSE-WAIT', 'ESTAB', 'LISTEN', 'TIME-WAIT', ]

    def columns(self,):
        return self.fields

    def check(self,):
        fetch = lambda: commands.getoutput("ss -an | cut -d' ' -f 1 | tail -n +2 | sort | uniq -c")
        data = {}
        result = []
        raw_lines = fetch().split('\n')
        for line in raw_lines:
            value = line.split()
            data[value[1].strip()] = int(value[0].strip())
        '''
        * check is there TCP connections in "field" state in last check
        if note set it to 0.
        * make output ordered as "fields" list
        '''
        for field in self.keys:
            if field in data:
                result.append(str(data[field]))
            else:
                result.append('0')
        return result



class NetTxRx(object):
    ''' Get upped iface names and read they Tx/Rx counters in bytes '''
    def __init__(self,):
        self.prevRX = 0
        self.prevTX = 0

    def columns(self,):
        return ['Net_tx', 'Net_rx', ]

    def check(self,):
        '''
        get network interface name which have ip addr
        which resolved fron  host FQDN.
        If we have network bonding or need to collect multiple iface
        statistic beter to change that behavior.
        '''
        data = commands.getoutput("/sbin/ifconfig -s | awk '{rx+=$4; tx+=$8} END {print rx, tx}'")
        logging.debug("TXRX output: %s", data)
        (rx, tx) = data.split(" ")
        rx = int(rx)
        tx = int(tx)
        
        if (self.prevRX == 0):
            tTX = 0
            tRX = 0
        else:
            tRX = rx - self.prevRX
            tTX = tx - self.prevTX
        self.prevRX = rx
        self.prevTX = tx
        
        return [tRX, tTX]



class Net(object):
    def __init__(self):
        self.recv = 0
        self.send = 0
        self.rgx = re.compile('\S+\s(\d+)\s(\d+)')

    def columns(self,):
        return ['Net_recv', 'Net_send']

    def check(self,):
        # Current data
        recv, send = 0, 0

        cmd = "cat /proc/net/dev | tail -n +3 | cut -d':' -f 1,2 --output-delimiter=' ' | awk '{print $1, $2, $10}'"
        logging.debug("Starting: %s", cmd)
        try:
            stat = Popen([cmd], stdout=PIPE, stderr=PIPE, shell=True)
        except Exception, e:
            logging.error("Error getting net metrics: %s", e)
            result = ['', '']

        else:
            err = stat.stderr.read()
            if err:
                logging.error("Error output: %s", err)
                result = ['', '']
            else:
                for el in stat.stdout:
                    m = self.rgx.match(el)
                    if m:
                        recv += int(m.group(1))
                        send += int(m.group(2))
                        logging.debug("Recv/send: %s/%s", recv, send)
                    else:
                        logging.debug("Not matched: %s", el)
                if self.recv:
                    result = [str(recv - self.recv), str(send - self.send)]
                else:
                    result = ['', '']

        self.recv, self.send = recv, send
        logging.debug("Result: %s", result)
        return result



# ===========================

def write(mesg):
    ''' console writing wraper '''
    sys.stdout.write('%s\n' % mesg)
    sys.stdout.flush()

def setup_logging():
    # Logging params
    LOG_FILENAME = os.path.dirname(__file__) + "_agent.log"
    if os.getenv("DEBUG"):
        level = logging.DEBUG
    else:
        level = logging.INFO
        
    FORMAT = "%(asctime)s - %(filename)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(filename=LOG_FILENAME, level=level, format=FORMAT)
    
    logging.info('Start agent')
    

def fixed_sleep(slp_interval,):
    # sleep 'interval' exclude processing time part
    global t_after
    if t_after is not None:
        t_delta = time.time() - t_after
        t_after = time.time()
        logging.debug('slp_interval:%s, t_delta:%s, slp_interval * 2 - t_delta = %s' % (slp_interval, t_delta, slp_interval * 2 - t_delta))
        if ((t_delta > slp_interval) & (slp_interval * 2 - t_delta > 0)):
            time.sleep(slp_interval * 2 - t_delta)
        else:
            if slp_interval * 2 - t_delta < 0:
                    logging.warn('[negative sleep time]')
            else:
                time.sleep(slp_interval)
    else:
        # first cycle iter
        t_after = time.time()
        time.sleep(slp_interval)


# TODO: 3 why this is required???
def check_cpu_mem(process_dict):
    '''
    Read 'ps' tool output and
    collect POSIX process %CPU,%MEM,VSZ,RSS values
    '''
    result = []
    for name in process_dict:
        result.extend(commands.getoutput('ps aux | grep ' + str(process_dict[name]['pid']) + ' | grep -v grep | awk \'{print $3";"$4";"$5";"$6}\'').split(';'))
    return result


proc_column = lambda name: [name + '_cpu_per', name + '_mem_per',
                                                name + '_mem_vsz',
                                                name + '_mem_rss', ]
unixtime = lambda: str(int(time.time()))

if __name__ == '__main__':
    # default params
    def_cfg_path = 'agent.cfg'
    c_interval = 1
    c_host = socket.getfqdn()
    custom_cfg = {'tail': [], 'call': []}
    c_tail = ''
    c_loglevel = ''
    c_local_start = int(time.time())
    c_start = c_local_start
    process = {}
    header = []
    dlmtr = ';'
    t_after = None
    
    #logger.debug("[debug] [agent] Start agent at host: %s\n" % c_host)
    
    # metrics we know about
    known_metrics = {
            'cpu-la': CpuLa(),
            'cpu-stat': CpuStat(),
            'mem':  Mem(),
            'io':  Io(),
            'net-retrans': NetRetrans(),
            'net-tx-rx': NetTxRx(),
            'net-tcp': NetTcp(),
            'disk': Disk(),
            'net': Net(),
            }
    
#    logger.debug('[debug] [agent] Start main loop')
    # parse options
    parser = OptionParser()
    parser.add_option('-c', '--config', dest='cfg_file', type='str',
                      help='Config file path, default is: ./' + def_cfg_path,
                                                        default=def_cfg_path)

    parser.add_option('-t', '--timestamp', dest='timestamp', type='int',
                      help='Caller timestamp for synchronization', default=c_local_start)
    (options, args) = parser.parse_args()

    c_start = options.timestamp
    logging.debug("Caller timestamp: %s", options.timestamp)

    # parse cfg file
    config = ConfigParser.ConfigParser()
    try:
        config.readfp(open(options.cfg_file))
    except IOError, msg:
        print >> sys.stderr, 'Can\'t read config file: ' + options.cfg_file
        sys.exit(1)

    # metric section
    c_metrics = []
    try:
        if config.has_option('metric', 'names'):
            c_metrics = config.get('metric', 'names').split(',')
    except ConfigParser.NoOptionError, msg:
        print >> sys.stderr, 'Can\'t parce config file, reason:\n', msg
        sys.exit(1)

    # main section
    if config.has_section('main'):
        if config.has_option('main', 'interval'):
            c_interval = config.getfloat('main', 'interval')
        if config.has_option('main', 'host'):
            c_host = config.get('main', 'host')
        if config.has_option('main', 'loglevel'):
            c_loglevel = config.get('main', 'loglevel')
        if config.has_option('main', 'start'):
            c_start = config.getint('main', 'start')

    logging.info('Agent params: %s, %s, %s' % (c_interval, c_host, c_loglevel))

    # custom section
    if config.has_section('custom'):
        if config.has_option('custom', 'tail'):
            custom_cfg['tail'] += config.get('custom', 'tail').split(',')
        if config.has_option('custom', 'call'):
            custom_cfg['call'] += config.get('custom', 'call').split(',')


    # parce cfg file - process section
    try:
        c_process = config.get('process', 'names').split(',')
        for proc_name in c_process:
            try:
                process[proc_name] = {'pid_file': config.get('process',
                                                    proc_name + '_pid_file')}
            except ConfigParser.NoOptionError:
                try:
                    process[proc_name] = {'pid': config.getint('process',
                                                        proc_name + '_pid')}
                except Exception, e:
                    print >> sys.stderr, \
                            'Can\'t parce config file *process* section:\n', e
                    sys.exit(1)
                pass
            pass
    except ConfigParser.NoOptionError, e:
        print '*process* section have to contain names and pids fields!\n', e
        sys.exit(1)
    except ConfigParser.NoSectionError:  # All fine, we can work without proc
        pass
    pass

    sync_time = str(c_start + (int(time.time()) - c_local_start))
#    header.extend(['start', c_host, unixtime()])  # start compile init header
    header.extend(['start', c_host, sync_time])  # start compile init header

    # check process, if it exist add columns to header
    for name in process:
        try:
            tmpPID = open(process[name]['pid_file'], 'r').read()
            # check that pid_file exist but is empty
            if not len(tmpPID) == 0:
                process[name]['pid'] = tmpPID.rstrip()
                if not os.path.exists('/proc/' + str(process[name]['pid'])):
                    print >> sys.stderr, 'Process with PID: ', \
                    process[name]['pid'], \
                    'doesn\'t exist. Associated with app:', name
                    sys.exit(1)
                else:
                    header.extend(proc_column(name))
            else:
                print >> sys.stderr, 'PID File is empty, path: ',
                process[name]['pid_file']
                sys.exit(1)
        # no 'pid_file' key in dict,
        # that mean that we shude use 'pid' property from conf file
        except KeyError:
            if not os.path.exists('/proc/' + str(process[name]['pid'])):
                print >> sys.stderr, 'Process with PID: ', \
                process[name]['pid'], \
                'doesn\'t exist, associated with app:', \
                name
                sys.exit(1)
            else:
                header.extend(proc_column(name))
        # can't read pid_file
        except IOError, e:
            print >> sys.stderr, 'Can\'t read PID file: ',
            process[name]['pid_file'], '\n', e
            sys.exit(1)
        pass

    # add metrics from config file to header
    for metric_name in c_metrics:
        if metric_name:
            header.extend(known_metrics[metric_name].columns())

    # add custom metrics from config file to header
#    print custom_cfg
    custom = Custom(**custom_cfg)
    header.extend(custom.columns())

    sys.stdout.write(dlmtr.join(header) + '\n')
    sys.stdout.flush()

    logging.debug(dlmtr.join(header))

    # check loop
    while True:
        logging.debug('Check')
        line = []
        sync_time = str(c_start + (int(time.time()) - c_local_start))
        line.extend([c_host, sync_time])
        for name in process:
            line.extend(check_cpu_mem(process))

        # known metrics
        for metric_name in c_metrics:
            try:
                data = known_metrics[metric_name].check()
            except Exception, e:
                logging.error('Can\'t fetch %s: %s', metric_name, e)
                data = ''
            line.extend(data)
        
        logging.debug("line: %s" % line)
        # custom commands
        line.extend(custom.check())
        
        # print result line
        row = dlmtr.join(line)
        logging.debug("str: %s" % row)
        sys.stdout.write(dlmtr.join(line) + '\n')
        sys.stdout.flush()

        fixed_sleep(c_interval)

