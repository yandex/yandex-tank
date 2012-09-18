#! /usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys
import time
import socket
import ConfigParser
import signal
import logging

from optparse import OptionParser

from metric.process import check_cpu_mem
from metric.cpu_la import CpuLa
from metric.cpu_stat import CpuStat
from metric.mem import Mem
from metric.net_retrans import NetRetrans
from metric.net_tx_rx import NetTxRx
from metric.net_tcp import NetTcp
from metric.io import Io
from metric.custom import Custom
from metric.disk import Disk
from metric.net import Net

def write(msg):
    sys.stdout.write('%s\n' % msg)
    sys.stdout.flush()

# Logging params
LOG_FILENAME = os.path.dirname(__file__) + "_agent.log"
if os.getenv("DEBUG"):
    level = logging.DEBUG
else:
    level = logging.INFO
    
FORMAT = "%(asctime)s - %(filename)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(filename=LOG_FILENAME, level=level, format=FORMAT)

logging.info('Start agent')

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

def exit_hand(signum, frame):
    logging.info('Signal handler called with signal %s: %s' % (signum, frame))
    exit(0)

# Handle signals
signal.signal(signal.SIGINT, exit_hand)
signal.signal(signal.SIGQUIT, exit_hand)
signal.signal(signal.SIGTERM, exit_hand)
signal.signal(signal.SIGHUP, exit_hand)
signal.signal(signal.SIGPIPE, exit_hand)
#signal.signal(signal.SIGSTOP, exit_hand)

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

proc_column = lambda name: [name + '_cpu_per', name + '_mem_per',
                                                name + '_mem_vsz',
                                                name + '_mem_rss', ]
unixtime = lambda: str(int(time.time()))

if __name__ == '__main__':
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
