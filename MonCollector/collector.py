from collections import defaultdict
from lxml import etree
from string import join, lower
from subprocess import PIPE, Popen
import ConfigParser
import base64
import logging
import os.path
import pwd
import re
import select
import signal
import sys
import tempfile
import time
import urllib2

class Config(object):
    def __init__(self, config):
        self.tree = etree.parse(config)

    def loglevel(self):
        '''Get log level from config file. Possible values: info, debug'''

        log_level = 'info'
        log_level_raw = self.tree.xpath('/Monitoring')[0].get('loglevel')
        if log_level_raw in ('info', 'debug'):
            log_level = log_level_raw
        return log_level


class AgentClient(object):
    def __init__(self, **kwargs):
        self.run = []
        self.port = 22
        for key, value in kwargs.iteritems():
            setattr(self, key, value)

        temp_config = tempfile.mkstemp('.cfg', 'agent_')
        self.path = {
            # Destination path on remote host
            'AGENT_REMOTE_FOLDER': '/var/tmp/lunapark_monitoring',

            # Source path on tank
            'AGENT_LOCAL_FOLDER': os.path.dirname(__file__) + '/agent/',
            'METRIC_LOCAL_FOLDER': os.path.dirname(__file__) + '/agent/metric',

            # Temp config path
            'TEMP_CONFIG': temp_config[1]
        }

        self.ssh_opts = ['-q', '-o', 'StrictHostKeyChecking=no', '-o', 'PasswordAuthentication=no', '-o', 'NumberOfPasswordPrompts=0', '-o', 'ConnectTimeout=5']
        user_id = pwd.getpwuid(os.getuid())[0]
        if (user_id == 'lunapark'):
            self.ssh_opts = ['-i', '/home/lunapark/.ssh/id_dsa'] + self.ssh_opts
        
        self.scp_opts = self.ssh_opts + ['-P', self.port]
        self.ssh_opts = self.ssh_opts + ['-p', self.port]

    def start(self):
        logging.debug('Start monitoring: %s' % self.host)
        self.run += ['-t', str(int(time.time()))]
        logging.debug(self.run)
        pipe = Popen(self.run, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        logging.debug("Started: %s", pipe)
        return pipe


    def create_agent_config(self, loglevel):
        # Creating config
        cfg = open(self.path['TEMP_CONFIG'], 'w')
        cfg.write('[main]\ninterval=%s\n' % self.interval)
        cfg.write('host=%s\n' % self.host)
        cfg.write('loglevel=%s\n' % loglevel)
        cfg.write('[metric]\nnames=%s\n' % self.metric)
        cfg.write('[custom]\n')
        for method in self.custom:
            if self.custom[method]:
                cfg.write('%s=%s\n' % (method, join(self.custom[method], ',')))
        
        cfg.close()

    def install(self, loglevel):
        """ Create folder and copy agent and metrics scripts to remote host """

        self.create_agent_config(loglevel)

        # getting remote temp dir
        cmd = ['ssh'] + self.ssh_opts + [self.host, self.python + ' -c "import tempfile; print tempfile.mkdtemp();"']
        logging.debug("Get remote temp dir: %s", cmd)
        pipe = Popen(cmd, stdout=PIPE, stderr=PIPE, bufsize=0)

        err = pipe.stderr.read().strip()
        if err:
            logging.error("[%s] ssh error: '%s'" % (self.host, err))
            return 1
        pipe.wait()
        logging.debug("Return code [%s]: %s" % (self.host, pipe.returncode))
        if pipe.returncode:
            return 1

        remote_dir = pipe.stdout.read().strip()
        if (remote_dir):
            self.path['AGENT_REMOTE_FOLDER'] = remote_dir
        logging.info("Remote dir at %s:%s", self.host, self.path['AGENT_REMOTE_FOLDER']);

        # Copy agent
        cmd = ['scp'] + self.scp_opts + [self.path['AGENT_LOCAL_FOLDER'] + 'agent.py', self.host + ':' + self.path['AGENT_REMOTE_FOLDER'] + '/agent.py']
        logging.debug("Copy agent to %s: %s" % (self.host, cmd))

        pipe = Popen(cmd, stdout=PIPE, bufsize=0)
        pipe.wait()
        logging.debug("AgentClient copy exitcode: %s", pipe.returncode)
        if pipe.returncode != 0:
            logging.error("AgentClient copy exitcode: %s", pipe.returncode)
            return pipe.returncode

        # Copy config
        cmd = ['scp'] + self.scp_opts + [self.path['TEMP_CONFIG'], self.host + ':' + self.path['AGENT_REMOTE_FOLDER'] + '/agent.cfg']
        logging.debug("[%s] Copy config: %s" % (cmd, self.host))
            
        pipe = Popen(cmd, stdout=PIPE, bufsize=0)
        pipe.wait()
        logging.debug("AgentClient copy config exitcode: %s", pipe.returncode)
        if pipe.returncode != 0:
            logging.error("AgentClient copy config exitcode: %s", pipe.returncode)
            return pipe.returncode

        # Copy metric
        cmd = ['scp'] + self.scp_opts + ['-r', self.path['METRIC_LOCAL_FOLDER'], self.host + ':' + self.path['AGENT_REMOTE_FOLDER'] + '/']
        logging.debug("[%s] Copy metric: %s" % (cmd, self.host))

        pipe = Popen(cmd, stdout=PIPE, bufsize=0)
        pipe.wait()
        logging.debug("Metrics copy exitcode: %s", pipe.returncode)
        if pipe.returncode != 0:
            logging.error("Metrics copy exitcode: %s", pipe.returncode)
            return pipe.returncode
      
        if os.getenv("DEBUG"):
            debug = "DEBUG=1"
        else:
            debug = ""
        self.run = ['ssh'] + self.ssh_opts + [self.host, '/usr/bin/env', debug, self.python, self.path['AGENT_REMOTE_FOLDER'] + '/agent.py', '-c', self.path['AGENT_REMOTE_FOLDER'] + '/agent.cfg']

        return 0

    def uninstall(self):
        """ Remove agent's files from remote host"""

        cmd = ['scp'] + self.scp_opts + [self.host + ':' + self.path['AGENT_REMOTE_FOLDER'] + "_agent.log", "monitoring_agent_" + self.host + ".log"]
        logging.debug("Copy agent log from %s: %s" % (self.host, cmd))
        remove = Popen(cmd, stdout=PIPE, bufsize=0)
        remove.wait()
        
        logging.info("Remove: %s" % self.path['TEMP_CONFIG'])
        if os.path.isfile(self.path['TEMP_CONFIG']):
            os.remove(self.path['TEMP_CONFIG'])

        cmd = ['ssh'] + self.ssh_opts + [self.host, 'rm', '-r', self.path['AGENT_REMOTE_FOLDER']]
        logging.debug("Uninstall agent from %s: %s" % (self.host, cmd))
        remove = Popen(cmd, stdout=PIPE, bufsize=0)
        remove.wait()

class MonitoringSender:
    # TODO: move it to data uploader
    def send_data(self, send_data):
        ''' Handle HTTP data send'''
        if not send_data:
            logging.debug("Nothing to send to server")
            time.sleep(0.5)
            return        
        addr = self.SEND_HOST + self.SEND_URI #+"&offline=1&debug=1" # FIXME: remove it
        logging.debug('HTTP Request: %s\tlength: %s' % (addr, len(send_data)))
        logging.debug('HTTP Request data: %s' % send_data.strip())
        req = urllib2.Request(addr, send_data)
        resp = urllib2.urlopen(req).read()
        logging.debug('HTTP Response: %s' % resp)
        if not self.reported_ok:
            logging.info("Sent first data OK")
            self.reported_ok = 1    

    def some_trash1(self):
        # Params for web storage
        config_file = '/etc/yandex-load-monitoring/config'
        config = ConfigParser.SafeConfigParser()
        config.read(config_file)
        
        try:
            SEND_TIME = config.getint('main', 'SEND_TIME')
            SEND_URI = config.get('main', 'SEND_URI') 
        except Exception, e:
            logging.exception(e)
            logging.error("Seems we have problem with " + config_file)
            able2send = 1
        
        try:
            SEND_HOST = config.get('main', 'SEND_HOST')
        except ConfigParser.NoOptionError, e:
            tank_config_file = '/etc/lunapark/db.conf'
            logging.warn("Seems we have no monitoring host setup, trying lunapark config: " + tank_config_file)
            tank_config = ConfigParser.SafeConfigParser()
            tank_config.read(tank_config_file)
            try:
                SEND_HOST = tank_config.get('DEFAULT', 'http_base')
            except ConfigParser.NoSectionError, e:
                logging.exception(e)
                logging.error("Seems we have one more problem with config, giving up.")
                able2send = 1
        
    def some_trash2(self, send_data):
        able2send = 1
        if able2send:
            try:
                self.send_data(send_data)
                send_data = ''
            except Exception, e:
                logging.warn("Recoverable error sending data to server: %s", e);
                try:
                    logging.info("Waiting 30 sec before retry...")
                    time.sleep(30)
                    self.send_data(send_data)
                    send_data = ''
                except Exception, e2:
                    logging.error("Fatal error sending data to server: %s", e2);
                    able2send = 0
    

class MonitoringCollector:
    def __init__(self, config, out_file):
        self.log=logging.getLogger(__name__)
        self.config = config
        self.out_file = out_file
        self.default_target = None
        self.agents = []
        self.agent_pipes = []
        self.filter_conf = {}

    def prepare(self):
        # Defining local storage
        self.store = sys.stdout
        if self.out_file:
            self.store = open(self.out_file, 'w')
        
        # Parse config
        agent_config = []
        if self.config:
            [agent_config, self.filter_conf] = self.getconfig(self.config, self.default_target)

        self.log.debug("filter_conf: %s", self.filter_conf)        
        conf = Config(self.config)
        logging.info('Logging level: %s' % conf.loglevel()) 
        
        # Filtering
        self.filter_mask = defaultdict(str)
        for host in self.filter_conf:
            self.filter_mask[host] = []
        self.log.debug("Filter mask: %s", self.filter_mask)
            
        # Creating agent for hosts
        logging.debug('Creating agents')
        for adr in agent_config:
            logging.debug('Creating agent: %s' % adr)
            agent = AgentClient(**adr)
            self.agents.append(agent)
        
        # Mass agents install
        logging.debug("Agents: %s" % self.agents)
        agents_cnt_before = len(self.agents)
        self.group_op('install', self.agents, conf.loglevel())
        
        if len(self.agents) != agents_cnt_before:
            logging.warn("Some targets can't be monitored")
        else:
            logging.info("All agents installed OK")
        
        # Nothing installed
        if not self.agents:
            raise RuntimeError("No agents was installed. Stop monitoring.")
        

    def start(self):
        self.inputs, self.outputs, self.excepts = [], [], []
        
        # Start N parallel agents 
        for a in self.agents:
            pipe = a.start()
            self.agent_pipes.append(pipe)
            self.outputs.append(pipe.stdout)
            self.excepts.append(pipe.stderr)     
            
        logging.debug("Pipes: %s", self.agent_pipes)
        
    def poll(self):
        send_data = ''
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
        for s in exceptional:
                data = s.readline()
                while data:
                    logging.error("Got exception [%s]: %s", s, data)
                    data = s.readline()                
    
        for s in readable:
            # Handle outputs
            data = s.readline()
            readable.remove(s)
            if not data:
                continue
            logging.debug("Got data: %s", data.strip())
    
            send_data += self.filter_unused_data(self.filter_conf, self.filter_mask, data)

            # TODO: make store one more data listener    
            self.store.write(send_data)
            self.store.flush()
        
        #TODO: notify liseners        
        return len(self.outputs)            
    
    def stop(self):
        logging.info("Initiating normal finish")
        for pipe in self.agent_pipes:
            logging.debug("Killing %s with %s", pipe.pid, signal.SIGINT)
            os.kill(pipe.pid, signal.SIGINT)
        self.group_op('uninstall', self.agents, '')
        
    def getconfig(self, filename, target_hint):
        default = {
            'System': 'csw,int',
            'CPU': 'user,system,iowait',
            'Memory': 'free,used',
            'Disk': 'read,write',
            'Net': 'recv,send',
        }
    
        default_metric = ['CPU', 'Memory', 'Disk', 'Net']
    
        try:
            tree = etree.parse(filename)
        except IOError, e:
            logging.error("Error loading config: %s", e)
            raise RuntimeError ("Can't read monitoring config %s" % filename)
    
        hosts = tree.xpath('/Monitoring/Host')
        names = defaultdict()
        config = []
        hostname = ''
        filter = defaultdict(str)
        for host in hosts:
            hostname = host.get('address')
            if hostname == '[target]':
                if not target_hint:
                    raise ValueError("Can't use [target] keyword with no target parameter specified")
                logging.info("Using target hint: %s", target_hint)
                hostname = target_hint
            stats = []
            custom = {'tail': [], 'call': [], }
            metrics_count = 0
            for metric in host:
                # known metrics
                if metric.tag in default.keys():
                    metrics_count += 1
                    m = default[metric.tag].split(',')
                    if metric.get('measure'):
                        m = metric.get('measure').split(',')
                    for el in m:
                        if not el:
                            continue;
                        stat = "%s_%s" % (metric.tag, el)
                        stats.append(stat)
                        agent_name = self.get_agent_name(metric.tag, el)
                        if agent_name:
                            names[agent_name] = 1
                # custom metric ('call' and 'tail' methods)
                if lower(str(metric.tag)) == 'custom':
                    metrics_count += 1
                    isdiff = metric.get('diff')
                    if not isdiff:
                        isdiff = 0
                    stat = "%s:%s:%s" % (base64.b64encode(metric.get('label')), base64.b64encode(metric.text), isdiff)
                    stats.append('Custom:' + stat)
                    custom[metric.get('measure')].append(stat)
    
            logging.debug("Metrics count: %s" % metrics_count)
            logging.debug("Host len: %s" % len(host))
            logging.debug("keys: %s" % host.keys())
            logging.debug("values: %s" % host.values())
    
            # use default metrics for host
            if metrics_count == 0:
                for metric in default_metric:
                    m = default[metric].split(',')
                    for el in m:
                        stat = "%s_%s" % (metric, el)
                        stats.append(stat)
                        agent_name = self.get_agent_name(metric, el)
                        if agent_name:
                            names[agent_name] = 1
    
            metric = join(names.keys(), ',')
            tmp = {}
    
            if metric:
                tmp.update({'metric': metric})
            else:
                tmp.update({'metric': 'cpu-stat'}) 
    
            if host.get('interval'):
                tmp.update({'interval': host.get('interval')})
            else:
                tmp.update({'interval': 1})
                    
            if host.get('priority'):
                tmp.update({'priority': host.get('priority')})
            else:
                tmp.update({'priority': 0})
    
            if host.get('port'):
                tmp.update({'port': host.get('port')})
            else:
                tmp.update({'port': '22'})
    
            if host.get('python'):
                tmp.update({'python': host.get('python')})
            else:
                tmp.update({'python': '/usr/bin/python'})
                
    
            tmp.update({'custom': custom})
    
            tmp.update({'host': hostname})
            filter[hostname] = stats
            config.append(tmp)
    
        return [config, filter]
    
    def group_op(self, command, agents, loglevel):
        """ Group install and uninstall for list of agents"""
        logging.debug("Group operation %s on agents: %s", command, agents);
    
        if command == 'uninstall':
            for agent in agents:
                logging.debug('Uninstall monitoring agent. Host: %s' % agent.host)
                agent.uninstall()
                logging.info("Remove: %s" % agent.path['TEMP_CONFIG'])
                if os.path.isfile(agent.path['TEMP_CONFIG']):
                    logging.warning("Seems uninstall failed to remove %s", agent.path['TEMP_CONFIG'])
                    os.remove(agent.path['TEMP_CONFIG'])
        if command == 'install':
            for agent in agents:
                logging.debug('Install monitoring agent. Host: %s' % agent.host)
                if agent.install(loglevel):
                    logging.debug("[%s] Cannot install. Remove: %s" % (agent.host, agent))
                    logging.info("Remove: %s" % agent.path['TEMP_CONFIG'])
                    if os.path.isfile(agent.path['TEMP_CONFIG']):
                        os.remove(agent.path['TEMP_CONFIG'])
                    agents.remove(agent)
            
    def filtering(self, mask, filter_list):
        host = filter_list[0]
        initial = [0, 1]
        out = ''
    #    print "mask: %s" % mask
    #    print "filter_list: %s " % filter_list
        res = []
        if mask[host]:
            keys = initial + mask[host]
            for key in keys:
                res.append(filter_list[key])
    #            print "key: %s, value: -%s-" % (key, filter_list[key])
                out += filter_list[key] + ';'
    #        print "res: %s" % res
    #    print res
    #    print join(res, ";")
        return join(res, ";")
            
    def filter_unused_data(self, filter_conf, filter_mask, data):
        out = ''
        # Filtering data
        keys = data.rstrip().split(';')
        if re.match('^start;', data): # make filter_conf mask
            host = keys[1]
            for i in xrange(3, len(keys)):
                if keys[i] in filter_conf[host]:
                    filter_mask[host].append(i - 1)
            
            out = 'start;'
            out += self.filtering(filter_mask, keys[1:]).rstrip(';') + '\n'
        elif re.match('^\[debug\]', data): # log debug output
            logging.debug('agent debug: %s' % data.rstrip())
        else:
            filtered = self.filtering(filter_mask, keys)
            if filtered:
                out = filtered + '\n' # filtering values
        #                    filtered = filtering(filter_mask, keys).rstrip(';')
        return out
    
    def get_agent_name(self, metric, param):
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

    
    
            
