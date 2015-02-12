"""Target monitoring via SSH"""

import ConfigParser
from collections import defaultdict
from xml.etree import ElementTree as etree
from subprocess import PIPE, Popen
import base64
import logging
import os.path
import re
import select
import signal
import sys
import tempfile
import time
import fcntl
import traceback
import getpass

import yandextank.core as tankcore


logger = logging.getLogger(__name__)


class Config(object):
    """Config reader helper"""

    def __init__(self, config):
        self.tree = etree.parse(config)

    def loglevel(self):
        """Get log level from config file. Possible values: info, debug"""
        log_level = 'info'
        log_level_raw = self.tree.find('./Monitoring').get('loglevel')
        if log_level_raw in ('info', 'debug'):
            log_level = log_level_raw
        return log_level


class SSHWrapper:
    """Separate SSH calls to be able to unit test the collector"""

    def __init__(self, timeout):
        self.ssh_opts = ['-q', '-o', 'StrictHostKeyChecking=no', '-o', 'PasswordAuthentication=no', '-o',
                         'NumberOfPasswordPrompts=0', '-o', 'ConnectTimeout=' + str(timeout)]
        self.scp_opts = []
        self.host = None
        self.port = None

    def set_host_port(self, host, port, username):
        """Set host and port to use"""
        self.host = host
        self.port = port
        self.username = username
        self.scp_opts = self.ssh_opts + ['-P', self.port]
        self.ssh_opts = self.ssh_opts + ['-C', '-p', self.port] + ['-l', self.username]

    def get_ssh_pipe(self, cmd):
        """Get open ssh pipe"""
        args = ['ssh'] + self.ssh_opts + [self.host] + cmd
        logger.debug('Executing: %s', args)
        return Popen(args, stdout=PIPE, stderr=PIPE, stdin=PIPE, bufsize=0, preexec_fn=os.setsid, close_fds=True)

    def get_scp_pipe(self, cmd):
        """Get open scp pipe"""
        args = ['scp'] + self.scp_opts + cmd
        logger.debug('Executing: %s', args)
        return Popen(args, stdout=PIPE, stderr=PIPE, stdin=PIPE, bufsize=0, preexec_fn=os.setsid, close_fds=True)


class AgentClient(object):
    """Agent client connection"""

    def __init__(self):
        self.run = []
        self.host = None

        self.port = 22
        self.ssh = None

        temp_config = tempfile.mkstemp('.cfg', 'agent_')
        os.close(temp_config[0])
        self.path = {
            # Destination path on remote host
            'AGENT_REMOTE_FOLDER': '/var/tmp/lunapark_monitoring',

            # Source path on tank
            'AGENT_LOCAL_FOLDER': os.path.dirname(__file__) + '/agent/',
            'METRIC_LOCAL_FOLDER': os.path.dirname(__file__) + '/agent/metric',

            # Temp config path
            'TEMP_CONFIG': temp_config[1]
        }
        self.interval = None
        self.metric = None
        self.custom = {}
        self.startups = []
        self.shutdowns = []
        self.python = '/usr/bin/env python2'
        self.username = getpass.getuser()

    def start(self):
        """Start remote agent"""
        logging.debug('Start monitoring: %s', self.host)
        if not self.run:
            raise ValueError("Empty run string")
        self.run += ['-t', str(int(time.time()))]
        logging.debug(self.run)
        pipe = self.ssh.get_ssh_pipe(self.run)
        logging.debug("Started: %s", pipe)
        return pipe

    def create_agent_config(self, loglevel):
        """Creating config"""
        try:
            float(self.interval)
        except:
            strn = "Monitoring interval parameter is in wrong format: '%s'. Only numbers allowed."
            raise ValueError(strn % self.interval)

        cfg = ConfigParser.ConfigParser()
        cfg.add_section('main')
        cfg.set('main', 'interval', self.interval)
        cfg.set('main', 'host', self.host)
        cfg.set('main', 'loglevel', loglevel)
        cfg.set('main', 'username', self.username)

        cfg.add_section('metric')
        cfg.set('metric', 'names', self.metric)

        cfg.add_section('custom')
        for method in self.custom:
            if self.custom[method]:
                cfg.set('custom', method, ','.join(self.custom[method]))

        cfg.add_section('startup')
        for idx, cmd in enumerate(self.startups):
            cfg.set('startup', "cmd%s" % idx, cmd)

        cfg.add_section('shutdown')
        for idx, cmd in enumerate(self.shutdowns):
            cfg.set('shutdown', "cmd%s" % idx, cmd)

        with open(self.path['TEMP_CONFIG'], 'w') as fds:
            cfg.write(fds)

        return self.path['TEMP_CONFIG']

    def install(self, loglevel):
        """Create folder and copy agent and metrics scripts to remote host"""
        logging.info("Installing monitoring agent at %s@%s...", self.username, self.host)
        agent_config = self.create_agent_config(loglevel)

        self.ssh.set_host_port(self.host, self.port, self.username)

        # getting remote temp dir
        cmd = [self.python + ' -c "import tempfile; print tempfile.mkdtemp();"']
        logging.debug("Get remote temp dir: %s", cmd)
        pipe = self.ssh.get_ssh_pipe(cmd)

        err = pipe.stderr.read().strip()
        if err:
            raise RuntimeError("[%s] ssh error: '%s'" % (self.host, err))
        pipe.wait()
        logging.debug("Return code [%s]: %s", self.host, pipe.returncode)
        if pipe.returncode:
            raise RuntimeError("Failed to get remote dir via SSH at %s@%s, code %s: %s" % (
                self.username, self.host, pipe.returncode, pipe.stdout.read().strip()))

        remote_dir = pipe.stdout.read().strip()
        if remote_dir:
            self.path['AGENT_REMOTE_FOLDER'] = remote_dir
        logging.debug("Remote dir at %s:%s", self.host, self.path['AGENT_REMOTE_FOLDER'])

        # Copy agent
        cmd = [self.path['AGENT_LOCAL_FOLDER'] + '/agent.py',
               self.username+'@'+'['+self.host+']' + ':' + self.path['AGENT_REMOTE_FOLDER']]
        logging.debug("Copy agent to %s: %s", self.host, cmd)

        pipe = self.ssh.get_scp_pipe(cmd)
        pipe.wait()
        logging.debug("AgentClient copy exitcode: %s", pipe.returncode)
        if pipe.returncode != 0:
            raise RuntimeError("AgentClient copy exitcode: %s" % pipe.returncode)

        # Copy config
        cmd = [
            self.path['TEMP_CONFIG'],
            '{user}@[{host}]:{dirname}/agent.cfg'.format(
                user=self.username,
                host=self.host,
                dirname=self.path['AGENT_REMOTE_FOLDER']
            )
        ]
        logging.debug("[%s] Copy config: %s", cmd, self.host)

        pipe = self.ssh.get_scp_pipe(cmd)
        pipe.wait()
        logging.debug("AgentClient copy config exitcode: %s", pipe.returncode)
        if pipe.returncode != 0:
            raise RuntimeError("AgentClient copy config exitcode: %s" % pipe.returncode)

        if os.getenv("DEBUG") or 1:
            debug = "DEBUG=1"
        else:
            debug = ""
        self.run = [debug, self.python, self.path['AGENT_REMOTE_FOLDER'] + '/agent.py', '-c',
                    self.path['AGENT_REMOTE_FOLDER'] + '/agent.cfg']
        return agent_config

    def uninstall(self):
        """Remove agent's files from remote host"""
        fhandle, log_file = tempfile.mkstemp('.log', "agent_" + self.host + "_")
        os.close(fhandle)
        cmd = [self.host + ':' + self.path['AGENT_REMOTE_FOLDER'] + "_agent.log", log_file]
        logging.debug("Copy agent log from %s@%s: %s", self.username, self.host, cmd)
        remove = self.ssh.get_scp_pipe(cmd)
        remove.wait()

        logging.info("Removing agent from: %s@%s...", self.username, self.host)
        cmd = ['rm', '-r', self.path['AGENT_REMOTE_FOLDER']]
        remove = self.ssh.get_ssh_pipe(cmd)
        remove.wait()
        return log_file


class MonitoringCollector:

    """Aggregate data from several collectors"""

    def __init__(self):
        self.config = None
        self.default_target = None
        self.agents = []
        self.agent_pipes = []
        self.filter_conf = {}
        self.listeners = []
        self.ssh_wrapper_class = SSHWrapper
        self.first_data_received = False
        self.send_data = ''
        self.artifact_files = []
        self.inputs, self.outputs, self.excepts = [], [], []
        self.filter_mask = defaultdict(str)
        self.ssh_timeout = 5

    def add_listener(self, obj):
        self.listeners.append(obj)

    def prepare(self):

        """Prepare for monitoring - install agents etc"""

        # Parse config
        agent_config = []
        if self.config:
            [agent_config, self.filter_conf] = self.getconfig(self.config, self.default_target)

        logger.debug("filter_conf: %s", self.filter_conf)

        # Filtering
        for host in self.filter_conf:
            self.filter_mask[host] = []
        logger.debug("Filter mask: %s", self.filter_mask)

        # Creating agent for hosts
        logging.debug('Creating agents')
        for adr in agent_config:
            logging.debug('Creating agent: %s', adr)
            agent = AgentClient()
            agent.host = adr['host']
            agent.username = adr['username']
            agent.python = adr['python']
            agent.metric = adr['metric']
            agent.port = adr['port']
            agent.interval = adr['interval']
            agent.custom = adr['custom']
            agent.startups = adr['startups']
            agent.shutdowns = adr['shutdowns']
            agent.ssh = self.ssh_wrapper_class(self.ssh_timeout)
            self.agents.append(agent)

        # Mass agents install
        logging.debug("Agents: %s", self.agents)

        conf = Config(self.config)
        for agent in self.agents:
            logging.debug('Install monitoring agent. Host: %s', agent.host)
            self.artifact_files.append(agent.install(conf.loglevel()))

    def start(self):
        """Start N parallel agents"""
        for agent in self.agents:
            pipe = agent.start()
            self.agent_pipes.append(pipe)

            fds = pipe.stdout.fileno()
            flags = fcntl.fcntl(fds, fcntl.F_GETFL)
            fcntl.fcntl(fds, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            self.outputs.append(pipe.stdout)

            fds = pipe.stderr.fileno()
            flags = fcntl.fcntl(fds, fcntl.F_GETFL)
            fcntl.fcntl(fds, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            self.excepts.append(pipe.stderr)

        logging.debug("Pipes: %s", self.agent_pipes)

    def poll(self):
        """Poll agents for data"""
        readable, writable, exceptional = select.select(self.outputs, self.inputs, self.excepts, 0)
        logging.debug("Streams: %s %s %s", readable, writable, exceptional)

        # if empty run - check children
        if (not readable) or exceptional:
            for pipe in self.agent_pipes:
                if pipe.returncode:
                    logging.debug("Child died returncode: %s", pipe.returncode)
                    self.outputs.remove(pipe.stdout)
                    self.agent_pipes.remove(pipe)

        # Handle exceptions
        for excepted in exceptional:
            data = excepted.readline()
            while data:
                logging.error("Got exception [%s]: %s", excepted, data)
                data = excepted.readline()

        while readable:
            to_read = readable.pop(0)
            # Handle outputs

            try:
                lines = to_read.read().split("\n")
            except IOError:
                logger.debug("No data available")
                lines = []

            for data in lines:
                logging.debug("Got data from agent: %s", data.strip())
                self.send_data += self.filter_unused_data(self.filter_conf, self.filter_mask, data)
                logging.debug("Data after filtering: %s", self.send_data)

        if not self.first_data_received and self.send_data:
            self.first_data_received = True
            logger.info("Monitoring received first data")
        else:
            self.send_collected_data()

        return len(self.outputs)

    def stop(self):
        """Shutdown agents"""
        logging.debug("Initiating normal finish")
        for pipe in self.agent_pipes:
            try:
                pipe.stdin.write("stop\n")
            except IOError as exc:
                logging.warn("Problems stopping agent: %s", traceback.format_exc(exc))

        time.sleep(1)

        for pipe in self.agent_pipes:
            if pipe.pid:
                first_try = True
                delay = 1
                while tankcore.pid_exists(pipe.pid):
                    if first_try:
                        logging.debug("Killing %s with %s", pipe.pid, signal.SIGTERM)
                        os.killpg(pipe.pid, signal.SIGTERM)
                        pipe.communicate()
                        first_try = False
                        time.sleep(0.1)
                    else:
                        time.sleep(delay)
                        delay *= 2
                        logging.warn("Killing %s with %s", pipe.pid, signal.SIGKILL)
                        os.killpg(pipe.pid, signal.SIGKILL)

        for agent in self.agents:
            self.artifact_files.append(agent.uninstall())

    def send_collected_data(self):
        """sends pending data set to listeners"""
        for listener in self.listeners:
            listener.monitoring_data(self.send_data)
        self.send_data = ''

    def get_host_config(self, filter_obj, host, names, target_hint):

        default = {
            'System': 'csw,int',
            'CPU': 'user,system,iowait',
            'Memory': 'free,cached,used',
            'Disk': 'read,write',
            'Net': 'recv,send',
        }

        default_metric = ['CPU', 'Memory', 'Disk', 'Net']

        hostname = host.get('address').lower()
        if hostname == '[target]':
            if not target_hint:
                raise ValueError("Can't use [target] keyword with no target parameter specified")
            logging.debug("Using target hint: %s", target_hint)
            hostname = target_hint.lower()
        stats = []
        startups = []
        shutdowns = []
        custom = {'tail': [], 'call': [], }
        metrics_count = 0
        for metric in host:
            # known metrics
            if metric.tag in default.keys():
                metrics_count += 1
                metr_val = default[metric.tag].split(',')
                if metric.get('measure'):
                    metr_val = metric.get('measure').split(',')
                for elm in metr_val:
                    if not elm:
                        continue
                    stat = "%s_%s" % (metric.tag, elm)
                    stats.append(stat)
                    agent_name = self.get_agent_name(metric.tag, elm)
                    if agent_name:
                        names[agent_name] = 1
            # custom metric ('call' and 'tail' methods)
            elif (str(metric.tag)).lower() == 'custom':
                metrics_count += 1
                isdiff = metric.get('diff')
                if not isdiff:
                    isdiff = 0
                stat = "%s:%s:%s" % (base64.b64encode(metric.get('label')), base64.b64encode(metric.text), isdiff)
                stats.append('Custom:' + stat)
                custom[metric.get('measure', 'call')].append(stat)
            elif (str(metric.tag)).lower() == 'startup':
                startups.append(metric.text)
            elif (str(metric.tag)).lower() == 'shutdown':
                shutdowns.append(metric.text)

        logging.debug("Metrics count: %s", metrics_count)
        logging.debug("Host len: %s", len(host))
        logging.debug("keys: %s", host.keys())
        logging.debug("values: %s", host.values())

        # use default metrics for host
        if metrics_count == 0:
            for metric in default_metric:
                metr_val = default[metric].split(',')
                for elm in metr_val:
                    stat = "%s_%s" % (metric, elm)
                    stats.append(stat)
                    agent_name = self.get_agent_name(metric, elm)
                    if agent_name:
                        names[agent_name] = 1

        metric = ','.join(names.keys())

        return {
            'metric': metric or 'cpu-stat',
            'interval': host.get('interval', 1),
            'priority': host.get('priority', 0),
            'port': host.get('port', '22'),
            'python': host.get('python', '/usr/bin/env python2'),
            'username': host.get('username', getpass.getuser()),
            'custom': custom,
            'host': hostname,
            'startups': startups,
            'shutdowns': shutdowns,

            # XXX: should be separate?
            'stats': {hostname: stats},
        }

    def getconfig(self, filename, target_hint):
        """Prepare config data"""

        try:
            tree = etree.parse(filename)
        except IOError as exc:
            logging.error("Error loading config: %s", exc)
            raise RuntimeError("Can't read monitoring config %s" % filename)

        hosts = tree.findall('./Monitoring/Host')
        names = defaultdict()
        config = []

        filter_obj = defaultdict(str)
        for host in hosts:
            host_config = self.get_host_config(host, names, target_hint)
            # XXX: why stats should be separated?
            filter_obj.update(host_config.pop('stats'))
            config.append(host_config)

        return [config, filter_obj]

    def filtering(self, mask, filter_list):
        """Filtering helper"""
        host = filter_list[0]
        initial = [0, 1]
        res = []
        if mask[host]:
            keys = initial + mask[host]
            for key in keys:
                try:
                    res.append(filter_list[key])
                except IndexError:
                    logger.warn("Problems filtering data: %s with %s", mask, len(filter_list))
                    return None
        return ';'.join(res)

    def filter_unused_data(self, filter_conf, filter_mask, data):
        """Filter unselected metrics from data"""
        logger.debug("Filtering data: %s", data)
        out = ''
        # Filtering data
        keys = data.rstrip().split(';')
        if re.match('^start;', data):  # make filter_conf mask
            host = keys[1]
            for i in range(3, len(keys)):
                if keys[i] in filter_conf[host]:
                    filter_mask[host].append(i - 1)
            logger.debug("Filter mask: %s", filter_mask)
            out = 'start;'
            out += self.filtering(filter_mask, keys[1:]).rstrip(';') + '\n'
        elif re.match('^\[debug\]', data):  # log debug output
            logging.debug('agent debug: %s', data.rstrip())
        else:
            filtered = self.filtering(filter_mask, keys)
            if filtered:
                out = filtered + '\n'  # filtering values
        return out

    def get_agent_name(self, metric, param):
        """Resolve metric name"""
        depend = {
            'CPU': {
                'idle': 'cpu-stat',
                'user': 'cpu-stat',
                'system': 'cpu-stat',
                'iowait': 'cpu-stat',
                'nice': 'cpu-stat'
            },
            'System': {
                'la1': 'cpu-la',
                'la5': 'cpu-la',
                'la15': 'cpu-la',
                'csw': 'cpu-stat',
                'int': 'cpu-stat',
                'numproc': 'cpu-stat',
                'numthreads': 'cpu-stat',
            },
            'Memory': {
                'free': 'mem',
                'used': 'mem',
                'cached': 'mem',
                'buff': 'mem',
            },
            'Disk': {
                'read': 'disk',
                'write': 'disk',
            },
            'Net': {
                'recv': 'net',
                'send': 'net',
                'tx': 'net-tx-rx',
                'rx': 'net-tx-rx',
                'retransmit': 'net-retrans',
                'estab': 'net-tcp',
                'closewait': 'net-tcp',
                'timewait': 'net-tcp',
            }
        }
        if depend[metric][param]:
            return depend[metric][param]
        else:
            return ''


class MonitoringDataListener:
    """Parent class for data listeners"""

    def __init__(self):
        pass

    def monitoring_data(self, data_string):
        """Notification about new monitoring data lines"""
        raise NotImplementedError()


class StdOutPrintMon(MonitoringDataListener):
    """Simple listener, writing data to stdout"""

    def __init__(self):
        MonitoringDataListener.__init__(self)

    def monitoring_data(self, data_string):
        sys.stdout.write(data_string)


class MonitoringDataDecoder:
    """The class that serves converting monitoring data lines to dict"""
    NA = 'n/a'

    def __init__(self):
        self.metrics = {}

    def decode_line(self, line):
        """convert mon line to dict"""
        is_initial = False
        data_dict = {}
        data = line.strip().split(';')
        timestamp = -1
        if data[0] == 'start':
            data.pop(0)  # remove 'start'
            host = data.pop(0)
            if not data:
                logging.warn("Wrong mon data line: %s", line)
            else:
                timestamp = data.pop(0)
                self.metrics[host] = []
                for metric in data:
                    if metric.startswith("Custom:"):
                        metric = base64.standard_b64decode(metric.split(':')[1])
                    self.metrics[host].append(metric)
                    data_dict[metric] = self.NA
                    is_initial = True
        else:
            host = data.pop(0)
            timestamp = data.pop(0)

            if host not in self.metrics.keys():
                raise ValueError("Host %s not in started metrics: %s" % (host, self.metrics))

            if len(self.metrics[host]) != len(data):
                raise ValueError("Metrics len and data len differs: %s vs %s" % (len(self.metrics[host]), len(data)))

            for metric in self.metrics[host]:
                data_dict[metric] = data.pop(0)

        logger.debug("Decoded data %s: %s", host, data_dict)
        return host, data_dict, is_initial, timestamp


# FIXME: 3 synchronize times between agent and collector better
