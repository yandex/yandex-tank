"""Target monitoring via SSH"""
import base64
import getpass
import logging
import os.path
import re
import tempfile
import time
from collections import defaultdict
from xml.etree import ElementTree as etree

from ...common.util import SecuredShell
from ...common.interfaces import MonitoringDataListener
import sys
if sys.version_info[0] < 3:
    import ConfigParser
else:
    import configparser as ConfigParser

logger = logging.getLogger(__name__)
logging.getLogger("paramiko.transport").setLevel(logging.WARNING)


def parse_xml(config):
    if os.path.exists(config):
        return etree.parse(config)
    else:
        return etree.fromstring(config)


class Config(object):
    """Config reader helper"""

    def __init__(self, config):
        self.tree = parse_xml(config)

    def loglevel(self):
        """Get log level from config file. Possible values: info, debug"""
        log_level = 'info'
        log_level_raw = self.tree.getroot().get('loglevel')
        if log_level_raw in ('info', 'debug'):
            log_level = log_level_raw
        return log_level


class AgentClient(object):
    """Agent client connection"""

    def __init__(self, adr, timeout):
        self.run = []
        self.host = adr['host']
        self.username = adr['username']
        self.python = adr['python']
        self.metric = adr['metric']
        self.port = adr['port']
        self.interval = adr['interval']
        self.custom = adr['custom']
        self.startups = adr['startups']
        self.shutdowns = adr['shutdowns']
        self.session = None
        self.buffer = ""
        self.ssh = SecuredShell(self.host, self.port, self.username, timeout)

        handle, cfg_path = tempfile.mkstemp('.cfg', 'agent_')
        os.close(handle)
        self.path = {
            # Destination path on remote host
            'AGENT_REMOTE_FOLDER': '/var/tmp/lunapark_monitoring',

            # Source path on tank
            'AGENT_LOCAL_FOLDER': os.path.dirname(__file__) + '/agent',
            'METRIC_LOCAL_FOLDER': os.path.dirname(__file__) + '/agent/metric',

            # Temp config path
            'TEMP_CONFIG': cfg_path
        }

    def start(self):
        """Start remote agent"""
        logger.debug('Start monitoring: %s', self.host)
        self.session = self.ssh.async_session(
            " ".join([
                "DEBUG=1", self.python, self.path['AGENT_REMOTE_FOLDER'] +
                '/agent.py', '-c', self.path['AGENT_REMOTE_FOLDER'] +
                '/agent.cfg', '-t', str(int(time.time()))
            ]))
        return self.session

    def read_maybe(self):
        chunk = self.session.read_maybe()
        if chunk:
            parts = chunk.rsplit('\n', 1)
            if len(parts) > 1:
                ready_chunk = self.buffer + parts[0] + '\n'
                self.buffer = parts[1]
                return ready_chunk
            else:
                self.buffer += parts[0]
                return None
        return None

    def create_agent_config(self, loglevel):
        """Creating config"""
        try:
            float(self.interval)
        except:
            raise ValueError(
                "Monitoring interval should be a number: '%s'" % self.interval)

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
        logger.info(
            "Installing monitoring agent at %s@%s...", self.username, self.host)

        # create remote temp dir
        cmd = self.python + ' -c "import tempfile; print tempfile.mkdtemp();"'
        logger.info("Creating temp dir on %s", self.host)
        try:
            out, errors, err_code = self.ssh.execute(cmd)
        except:
            logger.error(
                "Failed to install monitoring agent to %s",
                self.host,
                exc_info=True)
            return None
        if errors:
            logging.error("[%s] error: '%s'", self.host, errors)
            return None

        if err_code:
            logging.error(
                "Failed to create remote dir via SSH"
                " at %s@%s, code %s: %s" %
                (self.username, self.host, err_code, out.strip()))
            return None

        remote_dir = out.strip()
        if remote_dir:
            self.path['AGENT_REMOTE_FOLDER'] = remote_dir
        logger.debug(
            "Remote dir at %s:%s", self.host, self.path['AGENT_REMOTE_FOLDER'])

        # Copy agent and config
        agent_config = self.create_agent_config(loglevel)
        try:
            self.ssh.send_file(
                self.path['AGENT_LOCAL_FOLDER'] + '/agent.py',
                self.path['AGENT_REMOTE_FOLDER'] + '/agent.py')
            self.ssh.send_file(
                agent_config, self.path['AGENT_REMOTE_FOLDER'] + '/agent.cfg')
        except:
            logger.error(
                "Failed to install agent on %s", self.host, exc_info=True)
            return None
        return agent_config

    def uninstall(self):
        """
        Remove agent's files from remote host
        """
        if self.session:
            self.session.send("stop\n")
            self.session.close()
        fhandle, log_filename = tempfile.mkstemp(
            '.log', "agent_" + self.host + "_")
        os.close(fhandle)
        try:
            self.ssh.get_file(
                self.path['AGENT_REMOTE_FOLDER'] + "_agent.log", log_filename)
            self.ssh.rm_r(self.path['AGENT_REMOTE_FOLDER'])
        except:
            logger.error("Exception while uninstalling agent", exc_info=True)

        logger.info("Removing agent from: %s@%s...", self.username, self.host)
        return log_filename


class MonitoringCollector(object):
    """Aggregate data from several collectors"""

    def __init__(self):
        self.config = None
        self.default_target = None
        self.agents = []
        self.agent_sessions = []
        self.filter_conf = {}
        self.listeners = []
        self.first_data_received = False
        self.send_data = []
        self.artifact_files = []
        self.inputs, self.outputs, self.excepts = [], [], []
        self.filter_mask = defaultdict(str)
        self.ssh_timeout = 5
        self.load_start_time = None

    def add_listener(self, obj):
        self.listeners.append(obj)

    def prepare(self):
        """Prepare for monitoring - install agents etc"""

        # Parse config
        agent_config = []
        if self.config:
            [agent_config, self.filter_conf] = self.getconfig(
                self.config, self.default_target)
        loglevel = Config(self.config).loglevel()

        logger.debug("filter_conf: %s", self.filter_conf)

        # Filtering
        for host in self.filter_conf:
            self.filter_mask[host] = []
        logger.debug("Filter mask: %s", self.filter_mask)

        # Creating agent for hosts
        logger.debug('Creating agents')
        for adr in agent_config:
            logger.debug('Creating agent: %s', adr)
            agent = AgentClient(adr, timeout=self.ssh_timeout)
            logger.debug('Install monitoring agent. Host: %s', agent.host)
            agent_config = agent.install(loglevel)
            if agent_config:
                self.agents.append(agent)
                self.artifact_files.append(agent_config)

    def start(self):
        """Start N parallel agents"""
        [agent.start() for agent in self.agents]

    def poll(self):
        """Poll agents for data"""
        for agent in self.agents:
            block = agent.read_maybe()
            if not block:
                continue
            lines = block.split("\n")

            for data in lines:
                logger.debug("Got data from agent: %s", data.strip())
                self.send_data.append(
                    self.filter_unused_data(
                        self.filter_conf, self.filter_mask, data))
                logger.debug("Data after filtering: %s", self.send_data)

        if not self.first_data_received and self.send_data:
            self.first_data_received = True
            logger.info("Monitoring received first data")
        else:
            self.send_collected_data()

        return len(self.outputs)

    def stop(self):
        """Shutdown agents"""
        logger.debug("Uninstalling monitoring agents")
        for agent in self.agents:
            self.artifact_files.append(agent.uninstall())

    def send_collected_data(self):
        """sends pending data set to listeners"""
        [
            listener.monitoring_data(self.send_data)
            for listener in self.listeners
        ]
        self.send_data = []

    def get_host_config(self, host, target_hint):

        default = {
            'System': 'csw,int',
            'CPU': 'user,system,iowait',
            'Memory': 'free,cached,used',
            'Disk': 'read,write',
            'Net': 'recv,send,rx,tx',
        }

        default_metric = ['CPU', 'Memory', 'Disk', 'Net']

        names = defaultdict()

        hostname = host.get('address').lower()
        if hostname == '[target]':
            if not target_hint:
                raise ValueError(
                    "Can't use [target] keyword with "
                    "no target parameter specified")
            logger.debug("Using target hint: %s", target_hint)
            hostname = target_hint.lower()
        stats = []
        startups = []
        shutdowns = []
        custom = {
            'tail': [],
            'call': [],
        }
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
                stat = "%s:%s:%s" % (
                    base64.b64encode(metric.get('label')),
                    base64.b64encode(metric.text), isdiff)
                stats.append('Custom:' + stat)
                custom[metric.get('measure', 'call')].append(stat)
            elif (str(metric.tag)).lower() == 'startup':
                startups.append(metric.text)
            elif (str(metric.tag)).lower() == 'shutdown':
                shutdowns.append(metric.text)

        logger.debug("Metrics count: %s", metrics_count)
        logger.debug("Host len: %s", len(host))
        logger.debug("keys: %s", host.attrib.keys())
        logger.debug("values: %s", host.attrib.values())

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
        if not metric and not custom:
            metric = "cpu-stat"

        return {
            'metric': metric,
            'interval': host.get('interval', 1),
            'priority': host.get('priority', 0),
            'port': int(host.get('port', 22)),
            'python': host.get('python', '/usr/bin/env python2'),
            'username': host.get('username', getpass.getuser()),
            'custom': custom,
            'host': hostname,
            'startups': startups,
            'shutdowns': shutdowns,

            # XXX: should be separate?
            'stats': {
                hostname: stats
            },
        }

    def getconfig(self, filename, target_hint):
        """Prepare config data"""

        try:
            tree = parse_xml(filename)
        except IOError as exc:
            logger.error("Error loading config: %s", exc)
            raise RuntimeError("Can't read monitoring config %s" % filename)

        hosts = tree.findall('Host')
        config = []

        filter_obj = defaultdict(str)
        for host in hosts:
            host_config = self.get_host_config(host, target_hint)
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
                    logger.warn(
                        "Problems filtering data: %s with %s", mask,
                        len(filter_list))
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
            logger.debug('agent debug: %s', data.rstrip())
        else:
            # if we are in start_test() phase, check data's timestamp with load_start_time
            # and skip data collected before load_start_time
            if self.load_start_time is not None:
                try:
                    if int(keys[1]) >= self.load_start_time:
                        filtered = self.filtering(filter_mask, keys)
                        if filtered:
                            out = filtered + '\n'  # filtering values
                except IndexError:
                    pass
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


class StdOutPrintMon(MonitoringDataListener):
    """Simple listener, writing data to stdout"""

    def __init__(self):
        MonitoringDataListener.__init__(self)

    def monitoring_data(self, data_list):
        [sys.stdout.write(data) for data in data_list]


class MonitoringDataDecoder(object):
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
                logger.warn("Wrong mon data line: %s", line)
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
                raise ValueError(
                    "Host %s not in started metrics: %s" % (host, self.metrics))

            if len(self.metrics[host]) != len(data):
                raise ValueError(
                    "Metrics len and data len differs: %s vs %s" %
                    (len(self.metrics[host]), len(data)))

            for metric in self.metrics[host]:
                data_dict[metric] = data.pop(0)

        logger.debug("Decoded data %s: %s", host, data_dict)
        return host, data_dict, is_initial, timestamp


# FIXME: 3 synchronize times between agent and collector better
