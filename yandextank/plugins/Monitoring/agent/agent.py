#! /usr/bin/env python2
""" The agent bundle, contains all metric classes and agent running code """
import ConfigParser
import commands
import base64
import logging
import os
import glob
import re
import socket
import subprocess
import sys
import time
import traceback
import signal
from threading import Thread
from optparse import OptionParser

logger = logging.getLogger(__name__)


def signal_handler(sig, frame):
    """ required for non-tty python runs to interrupt """
    logger.warning("Got signal %s", sig)
    raise KeyboardInterrupt()


def set_sig_handler():
    uncatchable = ['SIG_DFL', 'SIGSTOP', 'SIGKILL']
    for sig_name in [
            s for s in dir(signal)
            if (s.startswith("SIG") and s not in uncatchable)
    ]:
        try:
            sig_num = getattr(signal, sig_name)
            signal.signal(sig_num, signal_handler)
        except Exception as e:
            logger.error("Can't set handler for %s, %s", sig_name, e)


class AbstractMetric:
    """ Parent class for all metrics """

    def __init__(self):
        pass

    def columns(self):
        """ methods should return list of columns provided by metric class """
        raise NotImplementedError()

    def check(self):
        """ methods should return list of values provided by metric class """
        raise NotImplementedError()


class CpuLa(AbstractMetric):
    def columns(self, ):
        return ['System_la1', 'System_la5', 'System_la15']

    def check(self, ):
        loadavg_file = open('/proc/loadavg', 'r')
        loadavg_data = loadavg_file.readline().strip().split()[:3]
        result = map(str, loadavg_data)
        loadavg_file.close()
        return result


class CpuStat(AbstractMetric):
    """ read /proc/stat and calculate amount of time
        the CPU has spent performing different kinds of work.
    """

    def __init__(self):
        AbstractMetric.__init__(self)
        self.prev_check = {}
        self.current_check = {}

    def columns(self, ):
        columns = [
            'System_csw', 'System_int', 'CPU_user', 'CPU_nice', 'CPU_system',
            'CPU_idle', 'CPU_iowait', 'CPU_irq', 'CPU_softirq',
            'System_numproc', 'System_numthreads'
        ]
        return columns

    def check(self, ):
        # resulting data array
        result = []

        try:
            proc_stat_file = open('/proc/stat', 'r')
            proc_stat_all = proc_stat_file.readlines()
            proc_stat_file.close()
        except Exception as exc:
            logger.error(
                'Error opening /proc/stat. Traceback: %s',
                traceback.format_exc(exc))
            result.append([''] * 9)
        else:
            # Parse data
            try:
                for stat in proc_stat_all:
                    if stat.startswith('cpu '):
                        self.current_check['cpu'] = map(
                            float, stat.split("\n")[0].split()[1:8])
                    if stat.startswith('ctxt '):
                        self.current_check['csw'] = float(stat.split()[1])
                    if stat.startswith('intr '):
                        self.current_check['intr'] = float(stat.split()[1])
            except Exception as exc:
                logger.error(
                    'Error parsing /proc/stat data. Traceback: %s',
                    traceback.format_exc(exc))

            # Context switches and interrups delta
            try:
                if not self.prev_check.get('csw') or not self.prev_check.get(
                        'intr'):
                    self.prev_check['csw'] = self.current_check['csw']
                    self.prev_check['intr'] = self.current_check['intr']
                    result.extend([''] * 2)
                else:
                    delta_csw = str(
                        self.current_check['csw'] - self.prev_check['csw'])
                    delta_intr = str(
                        self.current_check['intr'] - self.prev_check['intr'])
                    self.prev_check['csw'] = self.current_check['csw']
                    self.prev_check['intr'] = self.current_check['intr']
                    result.append(delta_csw)
                    result.append(delta_intr)
            except Exception as exc:
                logger.error(
                    'Error trying to count delta of cpu interrupts and csw. Traceback: %s',
                    traceback.format_exc(exc))
                result.extend([''] * 2)

            # CPU usage metrics delta
            try:
                if not self.prev_check.get('cpu'):
                    self.prev_check['cpu'] = self.current_check['cpu']
                    result.extend([''] * 7)
                else:
                    delta = []
                    cnt = 0
                    sum_val = 0
                    for metric in self.current_check['cpu']:
                        delta_cpu = self.current_check['cpu'][
                            cnt] - self.prev_check['cpu'][cnt]
                        sum_val += delta_cpu
                        delta.append(delta_cpu)
                        cnt += 1
                    cnt = 0
                    for metric in self.current_check['cpu']:
                        result.append(str((delta[cnt] / sum_val) * 100))
                        cnt += 1
                    self.prev_check['cpu'] = self.current_check['cpu']
            except Exception as exc:
                logger.error(
                    'Error trying to count delta of cpu usage metrics. Traceback: %s',
                    traceback.format_exc(exc))
                result.extend([''] * 7)

        # Numproc
        try:
            proc_dirs = os.listdir('/proc/')
            pids = []
            for element in proc_dirs:
                try:
                    element = int(element)
                except Exception as exc:
                    pass
                else:
                    pids.append(element)
        except Exception as exc:
            logger.error(
                'Error trying to count numprocs. Traceback: %s',
                traceback.format_exc(exc))
            result.append([''])
        else:
            result.append(str(len(pids)))

        # Numthreads
        try:
            loadavg_file = open('/proc/loadavg', 'r')
            numthreads = loadavg_file.readline().split()[3].split('/')[1]
            loadavg_file.close()
        except Exception as exc:
            logger.error(
                'Error opening /proc/loadavg to get numthreads. Traceback: %s',
                traceback.format_exc(exc))
            result.append([''])
        else:
            result.append(numthreads)

        # Sample : ['localhost', '1437493895', '1088.0', '728.0', '0.0', '0.0',
        # '6.25390869293', '93.6835522201', '0.0', '0.0', '0.0625390869293',
        # '239', '534']
        return result


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


class Custom(AbstractMetric):
    """ custom metrics: call and tail """

    def __init__(self, call, tail):
        AbstractMetric.__init__(self)
        self.call = call
        self.tail = tail
        self.diff_values = {}

    def columns(self, ):
        cols = []
        for el in self.tail:
            cols.append("Custom:" + el)
        for el in self.call:
            cols.append("Custom:" + el)
        return cols

    def check(self, ):
        res = []
        for el in self.tail:
            cmnd = base64.b64decode(el.split(':')[1])
            logger.debug("Run custom check: tail -n 1 %s", cmnd)
            output = subprocess.Popen(['tail', '-n', '1', cmnd],
                                      stdout=subprocess.PIPE).communicate()[0]
            res.append(self.diff_value(el, output.strip()))
        for el in self.call:
            cmnd = base64.b64decode(el.split(':')[1])

            logger.debug("Run custom check: %s", cmnd)
            output = subprocess.Popen(
                cmnd, shell=True, stdout=subprocess.PIPE).stdout.read()
            res.append(self.diff_value(el, output.strip()))
        logger.debug("Collected:\n%s", res)
        return res

    def diff_value(self, config_line, value):
        if not is_number(value):
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


class Disk(AbstractMetric):
    def __init__(self):
        AbstractMetric.__init__(self)
        self.read = 0
        self.write = 0
        self.devs = self._get_devs()

    def columns(self, ):
        return ['Disk_read', 'Disk_write']

    def check(self, ):
        # cluster size
        size = 512

        # Current data
        read, writed = 0, 0

        try:
            with open("/proc/diskstats") as mfd:
                stat = mfd.readlines()

            for el in stat:
                data = el.split()
                if data[2] in self.devs:
                    read += int(data[5])
                    writed += int(data[9])

            if self.read or self.write:
                result = [
                    str(size * (read - self.read)),
                    str(size * (writed - self.write))
                ]
            else:
                result = ['', '']

            self.read, self.write = read, writed

        except Exception as exc:
            logger.error("%s: %s", exc, traceback.format_exc(exc))
            result = ['', '']
        return result

    @staticmethod
    def _get_devs():
        try:
            with open("/proc/mounts") as mfd:
                mounts = mfd.readlines()
        except IOError as exc:
            logger.exception("Can't read block devices")
            return []
        logger.info("Mounts: %s", mounts)
        devs = []
        for mount in mounts:
            if mount.startswith("/dev"):
                parts = mount.split(" ")
                rp = os.path.realpath(parts[0])
                short_name = rp.split(os.sep)[-1]
                devs.append(short_name)
                # Fixed due to LVM volumes on dom0 machines
                # here we're trying to get block device name (even if mounted
                # device file exists)
                try:
                    for dirc in glob.glob("/sys/devices/virtual/block/*"):
                        logger.debug("Checking %s", dirc)
                        name_path = "%s/dm/name" % dirc
                        if os.path.exists(name_path):
                            logger.debug("Checking %s", dirc)
                            try:
                                with open(name_path) as fds:
                                    nam = fds.read().strip()
                                    logger.info("Test: %s/%s", nam, short_name)
                                    if nam == short_name:
                                        dsk_name = dirc.split(os.sep)[-1]
                                        logger.info("Found: %s", dsk_name)
                                        devs.append(dsk_name)
                                        break
                            except Exception as exc:
                                logger.info(
                                    "Failed: %s", traceback.format_exc(exc))
                except Exception as exc:
                    logger.info(
                        "Failed to get block device name via /sys/devices/: %s",
                        traceback.format_exc(exc))
        logger.info("Devs: %s", devs)
        return devs


class Mem(AbstractMetric):
    """
    Memory statistics
    """
    empty = ''

    def __init__(self):
        AbstractMetric.__init__(self)
        self.name = 'advanced memory usage'
        self.vars = (
            'MemUsed', 'Buffers', 'Cached', 'MemFree', 'Dirty', 'MemTotal')

    #        self.open('/proc/meminfo')

    def columns(self):
        columns = [
            'Memory_total', 'Memory_used', 'Memory_free', 'Memory_shared',
            'Memory_buff', 'Memory_cached'
        ]
        logger.info("Start. Columns: %s" % columns)
        return columns

    def check(self):
        result = []
        try:
            with open('/proc/meminfo') as f:
                meminfo = f.readlines()
            data = {}
            for name in self.vars:
                data[name] = 0
            for l in meminfo:
                if ':' not in l:
                    continue
                [name, raw_value] = l.split(':')
                data.update({name: long(raw_value.split()[0]) / 1024.0})
            data['MemUsed'] = data['MemTotal'] - data['MemFree'] - data[
                'Buffers'] - data['Cached']
            result = [
                data['MemTotal'], data['MemUsed'], data['MemFree'], 0,
                data['Buffers'], data['Cached']
            ]
        except Exception as e:
            logger.error("Can't get meminfo, %s", e, exc_info=True)
            result.append([self.empty] * 9)
        return map(str, result)


class NetRetrans(AbstractMetric):
    """ read netstat output and
    calculate tcp segment retransmition derivative """

    def __init__(self):
        AbstractMetric.__init__(self)
        self.retr_second = None
        self.retr_first = None
        self.fetch = None
        self.delta = []

    def columns(self, ):
        return ['Net_retransmit', ]

    def check(self, ):
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


class NetTcp(AbstractMetric):
    """ Read ss util output and count TCP socket's number grouped by state """

    def __init__(self):
        AbstractMetric.__init__(self)
        self.fields = [
            'Net_closewait',
            'Net_estab',
            'Net_timewait',
        ]
        self.keys = [
            'closed',
            'estab',
            'timewait',
        ]

    def columns(self, ):
        return self.fields

    def check(self, ):
        """
        * check is there TCP connections in "field" state in last check
        if note set it to 0.
        * make output ordered as "fields" list
        """

        def fetch():
            return commands.getoutput("ss -s | sed -ne '/^TCP:/p'")

        regex = ('(^[^(]+\()' '([^)]+)')
        matches = re.match(regex, fetch())
        raw = matches.group(2)

        data = {}
        result = []

        for i in raw.split(','):
            state, count = i.split()
            data[state] = count.split('/')[0]
        for field in self.keys:
            if field in data:
                result.append(str(data[field]))
            else:
                result.append('0')
        return result


class NetTxRx(AbstractMetric):
    """ Get upped iface names and read they Tx/Rx counters in bytes """

    def __init__(self):
        AbstractMetric.__init__(self)
        self.prev_rx = 0
        self.prev_tx = 0

    def columns(self, ):
        return [
            'Net_tx',
            'Net_rx',
        ]

    def check(self, ):
        """
        get network interface name which have ip addr
        which resolved fron  host FQDN.
        If we have network bonding or need to collect multiple iface
        statistic beter to change that behavior.
        """
        status, data = commands.getstatusoutput("/sbin/ifconfig -s")
        logger.debug("/sbin/ifconfig output is: %s", data)

        rx, tx = 0, 0

        if status == 0:
            try:
                lines = data.split('\n')

                def position(sample):
                    return lines[0].split().index(sample)

                rx_pos = position('RX-OK')
                tx_pos = position('TX-OK')

                for line in lines[1:]:
                    counters = line.split()
                    if counters[rx_pos].isdigit() and counters[tx_pos].isdigit(
                    ):
                        rx += int(counters[rx_pos])
                        tx += int(counters[tx_pos])
            except Exception as e:
                logger.error('Failed to parse ifconfig output %s: %s', data, e)

        logger.debug("Total RX/TX packets counters: %s", [str(rx), str(tx)])

        if self.prev_rx == 0:
            t_tx = 0
            t_rx = 0
        else:
            t_rx = rx - self.prev_rx
            t_tx = tx - self.prev_tx
        self.prev_rx = rx
        self.prev_tx = tx

        return [str(t_rx), str(t_tx)]


class Net(AbstractMetric):
    def __init__(self):
        AbstractMetric.__init__(self)
        self.recv = 0
        self.send = 0
        self.rgx = re.compile('\S+\s(\d+)\s(\d+)')

    def columns(self, ):
        return ['Net_recv', 'Net_send']

    def check(self, ):
        # Current data
        recv, send = 0, 0

        # TODO: change to simple file reading
        cmnd = "cat /proc/net/dev | tail -n +3 | cut -d':' -f 1,2 --output-delimiter=' ' | awk '{print $1, $2, $10}'"
        logger.debug("Starting: %s", cmnd)
        try:
            stat = subprocess.Popen([cmnd],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    shell=True)
        except Exception as exc:
            logger.error("Error getting net metrics: %s", exc)
            result = ['', '']

        else:
            err = stat.stderr.read()
            if err:
                logger.error("Error output: %s", err)
                result = ['', '']
            else:
                for elm in stat.stdout:
                    match = self.rgx.match(elm)
                    if match:
                        recv += int(match.group(1))
                        send += int(match.group(2))
                        logger.debug("Recv/send: %s/%s", recv, send)
                    else:
                        logger.debug("Not matched: %s", elm)
                if self.recv:
                    result = [str(recv - self.recv), str(send - self.send)]
                else:
                    result = ['', '']

        self.recv, self.send = recv, send
        logger.debug("Network recieved/sent bytes: %s", result)
        return result


# ===========================


class AgentWorker(Thread):
    dlmtr = ';'

    def __init__(self):
        Thread.__init__(self)
        self.last_run_ts = None
        self.startup_processes = []
        self.c_interval = 1
        self.tails = None
        self.calls = None
        self.metrics_collected = []
        self.startups = []
        self.shutdowns = []
        self.c_host = None
        self.c_local_start = None
        self.c_start = None
        self.daemon = True  # Thread auto-shutdown
        self.finished = False
        # metrics we know about
        self.known_metrics = {
            'cpu-la': CpuLa(),
            'cpu-stat': CpuStat(),
            'mem': Mem(),
            'net-retrans': NetRetrans(),
            'net-tx-rx': NetTxRx(),
            'net-tcp': NetTcp(),
            'disk': Disk(),
            'net': Net(),
        }

    @staticmethod
    def popen(cmnd):
        return subprocess.Popen(
            cmnd,
            bufsize=0,
            preexec_fn=os.setsid,
            close_fds=True,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

    def run(self):
        logger.info("Running startup commands")
        for cmnd in self.startups:
            logger.debug("Run: %s", cmnd)
            proc = self.popen(cmnd)
            self.startup_processes.append(proc)

        logger.info("Start polling thread")
        header = []

        sync_time = str(self.c_start + (int(time.time()) - self.c_local_start))
        header.extend(
            ['start', self.c_host, sync_time])  # start compile init header

        # add metrics from config file to header
        for metric_name in self.metrics_collected:
            if metric_name:
                header.extend(self.known_metrics[metric_name].columns())

        # add custom metrics from config file to header
        custom = Custom(self.calls, self.tails)
        header.extend(custom.columns())

        sys.stdout.write(self.dlmtr.join(header) + '\n')
        sys.stdout.flush()

        logger.debug(self.dlmtr.join(header))

        # check loop
        while not self.finished:
            logger.debug('Start check')
            line = []
            sync_time = str(
                self.c_start + (int(time.time()) - self.c_local_start))
            line.extend([self.c_host, sync_time])

            # known metrics
            for metric_name in self.metrics_collected:
                if not metric_name:
                    continue
                try:
                    data = self.known_metrics[metric_name].check()
                    if len(data) != len(
                            self.known_metrics[metric_name].columns()):
                        raise RuntimeError(
                            "Data len not matched columns count: %s" % data)
                except Exception as e:
                    logger.exception('Can\'t fetch %s', metric_name)
                    data = ['0'
                            ] * len(self.known_metrics[metric_name].columns())
                line.extend(data)

            logger.debug("line: %s" % line)
            # custom commands
            line.extend(custom.check())

            # print result line
            try:
                row = self.dlmtr.join(line)
                logger.debug("str: %s" % row)
                sys.stdout.write(row + '\n')
                sys.stdout.flush()
            except IOError as e:
                logger.error("Can't send data to collector, terminating, %s", e)
                self.finished = True

            self.fixed_sleep(self.c_interval)

        logger.info("Terminating startup commands")
        for proc in self.startup_processes:
            logger.debug("Terminate: %s", proc)
            os.killpg(proc.pid, signal.SIGTERM)

        logger.info("Running shutdown commands")
        for cmnd in self.shutdowns:
            logger.debug("Run: %s", cmnd)
            subprocess.call(cmnd, shell=True)

        logger.info("Worker thread finished")

    def fixed_sleep(self, slp_interval):
        """ sleep 'interval' exclude processing time part """
        delay = slp_interval
        if self.last_run_ts is not None:
            delta = time.time() - self.last_run_ts
            delay = slp_interval - delta
            logger.debug("Sleep for: %s (delta %s)", delay, delta)

        time.sleep(delay if delay > 0 else 0)
        self.last_run_ts = time.time()


class AgentConfig:
    def __init__(self, def_cfg_path):
        self.c_interval = 1
        self.c_host = socket.getfqdn()
        logger.info("Start agent at host: %s\n" % self.c_host)
        self.c_start = None
        self.c_local_start = int(time.time())
        self.metrics_collected = []
        self.calls = []
        self.tails = []
        self.startups = []
        self.shutdowns = []

        options = self.parse_options(def_cfg_path)
        self.parse_config(options.cfg_file)

    def parse_options(self, def_cfg_path):
        # parse options
        parser = OptionParser()
        parser.add_option(
            '-c',
            '--config',
            dest='cfg_file',
            type='str',
            help='Config file path, default is: ./' + def_cfg_path,
            default=def_cfg_path)

        parser.add_option(
            '-t',
            '--timestamp',
            dest='timestamp',
            type='int',
            help='Caller timestamp for synchronization',
            default=self.c_local_start)
        (options, args) = parser.parse_args()

        self.c_start = options.timestamp
        logger.debug("Caller timestamp: %s", options.timestamp)

        return options

    def parse_config(self, cfg_file='agent.cfg'):
        # parse cfg file
        config = ConfigParser.ConfigParser()
        config.readfp(open(cfg_file))

        # metric section
        if config.has_option('metric', 'names'):
            self.metrics_collected = config.get('metric', 'names').split(',')

        # main section
        if config.has_section('main'):
            if config.has_option('main', 'interval'):
                self.c_interval = config.getfloat('main', 'interval')
            if config.has_option('main', 'host'):
                self.c_host = config.get('main', 'host')
            if config.has_option('main', 'start'):
                self.c_start = config.getint('main', 'start')

        logger.info('Agent params: %s, %s' % (self.c_interval, self.c_host))

        # custom section
        if config.has_section('custom'):
            if config.has_option('custom', 'tail'):
                self.tails += config.get('custom', 'tail').split(',')
            if config.has_option('custom', 'call'):
                self.calls += config.get('custom', 'call').split(',')

        if config.has_section('startup'):
            for option in config.options('startup'):
                if option.startswith('cmd'):
                    self.startups.append(config.get('startup', option))

        if config.has_section('shutdown'):
            for option in config.options('shutdown'):
                if option.startswith('cmd'):
                    self.shutdowns.append(config.get('shutdown', option))

    def prepare_worker(self, wrk):
        # populate
        wrk.c_start = self.c_start
        wrk.c_local_start = self.c_local_start
        wrk.c_interval = self.c_interval
        wrk.c_host = self.c_host
        wrk.metrics_collected = self.metrics_collected
        wrk.calls = self.calls
        wrk.tails = self.tails
        wrk.startups = self.startups
        wrk.shutdowns = self.shutdowns


if __name__ == '__main__':
    fname = os.path.dirname(__file__) + "_agent.log"
    level = logging.DEBUG

    fmt = "%(asctime)s - %(filename)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(filename=fname, level=level, format=fmt)

    set_sig_handler()

    worker = AgentWorker()

    agent_config = AgentConfig('agent.cfg')
    agent_config.prepare_worker(worker)

    worker.start()

    try:
        logger.debug("Check for stdin shutdown command")
        cmd = sys.stdin.readline()
        if cmd:
            logger.info("Stdin cmd received: %s", cmd)
            worker.finished = True
    except KeyboardInterrupt:
        logger.info("Interrupted")
        worker.finished = True
    except:
        logger.error("Unexpected exception, try to shutdown", exc_info=True)
        worker.finished = True
    while worker.isAlive():
        try:
            logger.debug("Join the worker thread, waiting for cleanup")
            worker.join(10)
            if worker.isAlive():
                logger.error(
                    "Worker have not finished shutdown in "
                    "10 seconds, going to exit anyway")
                sys.exit(1)
        except KeyboardInterrupt:
            if not worker.isAlive():
                logger.info("Worker finished")
            else:
                logger.info("Waiting for worker process was interrupted")
