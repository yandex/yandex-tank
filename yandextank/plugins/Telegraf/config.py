from xml.etree import ElementTree as etree
import os.path
import getpass
import logging
import tempfile
import ConfigParser

from ..Telegraf.decoder import decoder

logger = logging.getLogger(__name__)


class ConfigManager(object):
    """
    Config reader and parser helper.
    XML support
    """

    @staticmethod
    def parse_xml(config):
        if os.path.exists(config):
            return etree.parse(config)
        else:
            return etree.fromstring(config)

    def getconfig(self, filename, target_hint):
        """Prepare config data."""
        try:
            tree = self.parse_xml(filename)
        except IOError as exc:
            logger.error("Error loading config: %s", exc)
            raise RuntimeError("Can't read monitoring config %s" % filename)
        hosts = tree.findall('Host')
        config = []
        for host in hosts:
            host_config = self.get_host_config(host, target_hint)
            config.append(host_config)
        return config

    def get_host_config(self, host, target_hint):
        hostname = host.get('address').lower()
        if hostname == '[target]':
            if not target_hint:
                raise ValueError(
                    "Can't use `[target]` keyword with no target parameter specified")
            logger.debug("Using target hint: %s", target_hint)
            hostname = target_hint.lower()
        custom = []
        startups = []
        shutdowns = []
        for metric in host:
            # custom metrics
            if (str(metric.tag)).lower() == 'custom':
                isdiff = metric.get('diff', 0)
                cmd = {
                    'cmd': metric.text,
                    'label': metric.get('label'),
                    'diff': isdiff
                }
                custom.append(cmd)
            elif (str(metric.tag)).lower() == 'startup':
                startups.append(metric.text)
            elif (str(metric.tag)).lower() == 'shutdown':
                shutdowns.append(metric.text)

        return {
            'interval': host.get('interval', 1),
            'port': int(host.get('port', 22)),
            'python': host.get('python', '/usr/bin/env python2'),
            'username': host.get('username', getpass.getuser()),
            'telegraf': host.get('telegraf', '/usr/bin/telegraf'),
            'comment': host.get('comment', ''),
            'custom': custom,
            'host': hostname,
            'startup': startups,
            'shutdown': shutdowns
        }


class AgentConfig(object):
    """ Agent config generator helper """

    def __init__(self, config):
        self.monitoring_data_output = None
        self.host = config['host']
        self.custom = config['custom']
        self.startups = config['startup']
        self.shutdowns = config['shutdown']
        self.interval = config['interval']
        self.comment = config['comment']

    def create_startup_config(self):
        cfg_path = "agent_startup_{}.cfg".format(self.host)
        if os.path.isfile(cfg_path):
            logger.info(
                'Found agent startup config file in working directory with the same name as created for host %s'
                'Creating new one via tempfile. This will affect predictable filenames for agent artefacts',
                self.host)
            handle, cfg_path = tempfile.mkstemp('.cfg', 'agent_')
            os.close(handle)
        try:
            config = ConfigParser.RawConfigParser()
            config.add_section('startup')
            for idx, cmd in enumerate(self.startups):
                config.set('startup', "cmd%s" % idx, cmd)

            config.add_section('shutdown')
            for idx, cmd in enumerate(self.shutdowns):
                config.set('shutdown', "cmd%s" % idx, cmd)
            with open(cfg_path, 'w') as fds:
                config.write(fds)
        except Exception as exc:
            logger.error(
                'Error trying to create monitoring startups config. Malformed? %s',
                exc,
                exc_info=True)
        return cfg_path

    def create_collector_config(self, workdir):
        """Creating config"""
        cfg_path = "agent_{}.cfg".format(self.host)
        if os.path.isfile(cfg_path):
            logger.info(
                'Found agent config file in working directory with the same name as created for host %s'
                'Creating new one via tempfile. This will affect predictable filenames for agent artefacts',
                self.host)
            handle, cfg_path = tempfile.mkstemp('.cfg', 'agent_')
            os.close(handle)

        self.monitoring_data_output = "{remote_folder}/monitoring.rawdata".format(
            remote_folder=workdir)
        try:
            config = ConfigParser.RawConfigParser()
            config.add_section("global_tags")
            config.add_section("agent")
            config.set("agent",
                       "interval",
                       "'{interval}s'".format(interval=self.interval))
            config.set("agent", "round_interval", "true")
            config.set("agent", "flush_interval", "'1s'")
            config.set("agent", "collection_jitter", "'0s'")
            config.set("agent", "flush_jitter", "'0s'")
            #outputs
            config.add_section("[outputs.file]")
            config.set("[outputs.file]",
                       "files",
                       "['{config}']".format(
                           config=self.monitoring_data_output))
            config.set("[outputs.file]", "data_format", "'json'")
            #inputs
            config.add_section("[inputs.mem]")
            config.add_section("[inputs.cpu]")
            config.set("[inputs.cpu]", "fielddrop", '["time_*"]')
            config.add_section("[inputs.disk]")
            config.set("[inputs.disk]", "mount_points", '["/"]')
            config.set("[inputs.disk]", "ignore_fs", '["tmpfs", "devtmpfs"]')
            config.add_section("[inputs.diskio]")
            config.set("[inputs.diskio]", "devices", '["vda", "sda"]')
            config.add_section("[inputs.net]")
            config.set("[inputs.net]", "interfaces", '["eth0"]')
            config.set("[inputs.net]", "fielddrop",
                       '["icmp*", "ip*", "udplite*", "tcp*", "udp*"]')
            config.add_section("[inputs.netstat]")
            config.add_section("[inputs.system]")
            config.set("[inputs.system]", "fielddrop",
                       '["n_users", "uptime_format"]')
            config.add_section("[inputs.processes]")
            config.add_section("[inputs.kernel]")
            config.set("[inputs.kernel]", "fielddrop", '["boot_time"]')

            with open(cfg_path, 'w') as fds:
                config.write(fds)

            inputs = ""
            for cmd in self.custom:
                inputs += "[[inputs.exec]]\n"
                inputs += 'commands = [\'\'\' /bin/bash -c "{}" \'\'\']\n'.format(
                    cmd.get('cmd'))
                inputs += "data_format = 'value'\n"
                inputs += "data_type = 'integer'\n"
                inputs += "name_prefix = '{}_'\n\n".format(cmd.get('label'))
                if cmd['diff']:
                    decoder.diff_metrics.append(decoder.find_common_names(
                        cmd.get('label') + "_exec_value"))

            with open(cfg_path, 'a') as fds:
                fds.write(inputs)
        except Exception as exc:
            logger.error(
                'Error trying to create monitoring config. Malformed? %s',
                exc,
                exc_info=True)
        return cfg_path
