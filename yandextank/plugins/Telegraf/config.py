from xml.etree import ElementTree as etree
import os.path
import getpass
import logging
import tempfile
from future.utils import iteritems
from ..Telegraf.decoder import decoder
import sys
if sys.version_info[0] < 3:
    import ConfigParser
else:
    import configparser as ConfigParser

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
        defaults = {
            "CPU": {
                "name": '[inputs.cpu]',
                "percpu": 'false',
                "fielddrop": '["time_*", "usage_guest_nice"]'
            },
            "Memory": {
                "name": '[inputs.mem]',
                "fielddrop":
                '["active", "inactive", "total", "used_per*", "avail*"]',
            },
            "Disk": {
                "name": '[inputs.diskio]',
                "devices": '[{devices}]'.format(
                    devices=",".join(
                        ['"vda%s","sda%s"' % (num, num) for num in range(6)])),
            },
            "Net": {
                "name": '[inputs.net]',
                "interfaces": '[{interfaces}]'.format(
                    interfaces=",".join(
                        ['"eth%s"' % (num) for num in range(6)])),
                "fielddrop":
                '["icmp*", "ip*", "udplite*", "tcp*", "udp*", "drop*", "err*"]',
            },
            "Nstat": {
                "name": '[inputs.nstat]',
                "fieldpass": '["TcpRetransSegs"]',
            },
            "Netstat": {
                "name": '[inputs.netstat]',
            },
            "NetResponse": {
                "name": '[inputs.net_response]',
                "protocol": '"tcp"',
                "address": '":80"',
                "timeout": '"1s"'
            },
            "System": {
                "name": '[inputs.system]',
                "fielddrop": '["n_users", "n_cpus", "uptime*"]',
            },
            "Kernel": {
                "name": '[inputs.kernel]',
                "fielddrop": '["boot_time"]',
            }
        }
        defaults_enabled = ['CPU', 'Memory', 'Disk', 'Net', 'System', 'Kernel']
        defaults_boolean = [
            'percpu', 'round_interval', 'fielddrop', 'fieldpass', 'interfaces',
            'devices'
        ]
        hostname = host.get('address').lower()
        if hostname == '[target]':
            if not target_hint:
                raise ValueError(
                    "Can't use `[target]` keyword with no target parameter specified"
                )
            logger.debug("Using target hint: %s", target_hint)
            hostname = target_hint.lower()
        custom = []
        startups = []
        shutdowns = []
        # agent defaults
        host_config = {}
        for metric in host:
            if str(metric.tag) in defaults.keys():
                for key in defaults[metric.tag]:
                    if key != 'name' and key not in defaults_boolean:
                        value = metric.get(key, None)
                        if value:
                            defaults[metric.tag][key] = "'{value}'".format(
                                value=value)
                    elif key in defaults_boolean:
                        value = metric.get(key, None)
                        if value:
                            defaults[metric.tag][key] = "{value}".format(
                                value=value)
                host_config[metric.tag] = defaults[metric.tag]
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
        if len(host_config) == 0:
            logging.info('Empty host config, using defaults')
            for section in defaults_enabled:
                host_config[section] = defaults[section]
        return {
            'host_config': host_config,
            'port': int(host.get('port', 22)),
            'python': host.get('python', '/usr/bin/env python2'),
            'interval': host.get('interval', 1),
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

    def __init__(self, config, old_style_configs):
        self.host = config['host']
        self.custom = config['custom']
        self.startups = config['startup']
        self.shutdowns = config['shutdown']
        self.interval = config['interval']
        self.comment = config['comment']
        self.host_config = config['host_config']
        self.old_style_configs = old_style_configs

    def create_startup_config(self):
        """ Startup and shutdown commands config
        Used by agent.py on the target

        """
        cfg_path = "agent_startup_{}.cfg".format(self.host)
        if os.path.isfile(cfg_path):
            logger.info(
                'Found agent startup config file in working directory with the same name as created for host %s.\n'
                'Creating new one via tempfile. This will affect predictable filenames for agent artefacts',
                self.host)
            handle, cfg_path = tempfile.mkstemp('.cfg', 'agent_')
            os.close(handle)
        try:
            config = ConfigParser.RawConfigParser()
            # FIXME incinerate such a string formatting inside a method call
            # T_T
            config.add_section('startup')
            [
                config.set('startup', "cmd%s" % idx, cmd)
                for idx, cmd in enumerate(self.startups)
            ]
            config.add_section('shutdown')
            [
                config.set('shutdown', "cmd%s" % idx, cmd)
                for idx, cmd in enumerate(self.shutdowns)
            ]
            with open(cfg_path, 'w') as fds:
                config.write(fds)

        except Exception as exc:
            logger.error(
                'Error trying to create monitoring startups config. Malformed? %s',
                exc,
                exc_info=True)
        return cfg_path

    def create_custom_exec_script(self):
        """ bash script w/ custom commands inside
        inspired by half a night trying to avoid escaping bash special characters

        """
        cfg_path = "agent_customs_{}.cfg".format(self.host)
        if os.path.isfile(cfg_path):
            logger.info(
                'Found agent custom execs config file in working directory with the same name as created for host %s.\n'
                'Creating new one via tempfile. This will affect predictable filenames for agent artefacts',
                self.host)
            handle, cfg_path = tempfile.mkstemp('.sh', 'agent_customs_')
            os.close(handle)

        cmds = ""
        for idx, cmd in enumerate(self.custom):
            cmds += "-{idx}) {cmd};;\n".format(idx=idx, cmd=cmd['cmd'])
        customs_script = """
        #!/bin/sh
        while :
        do
            case "$1" in
            {cmds}
            *) break;;
            esac
            shift
        done
        """.format(cmds=cmds)

        with open(cfg_path, 'w') as fds:
            fds.write(customs_script)
        return cfg_path

    def create_collector_config(self, workdir):
        """ Telegraf collector config,
        toml format

        """
        cfg_path = "agent_collector_{}.cfg".format(self.host)
        if os.path.isfile(cfg_path):
            logger.info(
                'Found agent config file in working directory with the same name as created for host %s.\n'
                'Creating new one via tempfile. This will affect predictable filenames for agent artefacts',
                self.host)
            handle, cfg_path = tempfile.mkstemp('.cfg', 'agent_collector_')
            os.close(handle)

        self.monitoring_data_output = "{remote_folder}/monitoring.rawdata".format(
            remote_folder=workdir)

        defaults_old_enabled = ['CPU', 'Memory', 'Disk', 'Net', 'System']

        try:
            config = ConfigParser.RawConfigParser()

            config.add_section("global_tags")
            config.add_section("agent")
            config.set(
                "agent",
                "interval",
                "'{interval}s'".format(interval=self.interval))
            config.set("agent", "round_interval", "true")
            config.set("agent", "flush_interval", "'1s'")
            config.set("agent", "collection_jitter", "'0s'")
            config.set("agent", "flush_jitter", "'1s'")

            for section in self.host_config.keys():
                # telegraf-style config
                if not self.old_style_configs:
                    config.add_section(
                        "{section_name}".format(
                            section_name=self.host_config[section]['name']))
                    for key, value in iteritems(self.host_config[section]):
                        if key != 'name':
                            config.set(
                                "{section_name}".format(
                                    section_name=self.host_config[section][
                                        'name']),
                                "{key}".format(key=key),
                                "{value}".format(value=value))
                # monitoring-style config
                else:
                    if section in defaults_old_enabled:
                        config.add_section(
                            "{section_name}".format(
                                section_name=self.host_config[section]['name']))
                        for key, value in iteritems(self.host_config[section]):
                            if key in [
                                    'fielddrop', 'fieldpass', 'percpu',
                                    'devices', 'interfaces'
                            ]:
                                config.set(
                                    "{section_name}".format(
                                        section_name=self.host_config[section][
                                            'name']),
                                    "{key}".format(key=key),
                                    "{value}".format(value=value))

            # outputs
            config.add_section("[outputs.file]")
            config.set(
                "[outputs.file]",
                "files",
                "['{config}']".format(config=self.monitoring_data_output))
            config.set("[outputs.file]", "data_format", "'json'")

            with open(cfg_path, 'w') as fds:
                config.write(fds)

            # dirty hack, this allow to avoid bash escape quoting, we're pushing shell script w/ arguments
            # index of argument is index of custom metric in our config
            inputs = ""
            for idx, cmd in enumerate(self.custom):
                inputs += "[[inputs.exec]]\n"
                inputs += "commands = ['/bin/sh {workdir}/agent_customs.sh -{idx}']\n".format(
                    workdir=workdir, idx=idx)
                inputs += "data_format = 'value'\n"
                inputs += "data_type = 'float'\n"
                inputs += "name_prefix = '{}_'\n\n".format(cmd.get('label'))
                if cmd['diff']:
                    decoder.diff_metrics['custom'].append(
                        decoder.find_common_names(cmd.get('label')))

            with open(cfg_path, 'a') as fds:
                fds.write(inputs)

        except Exception as exc:
            logger.error(
                'Error trying to create monitoring config. Malformed? %s',
                exc,
                exc_info=True)
        return cfg_path
