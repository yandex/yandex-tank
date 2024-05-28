import os.path
import getpass
import logging
import tempfile
import pkg_resources
from copy import deepcopy
from ..Telegraf.decoder import decoder
from .config_parser import parse_xml, parse_yaml, ParseError, TARGET_HINT_PLACEHOLDER
from yandextank.common.util import read_resource
import configparser
from requests.structures import CaseInsensitiveDict

logger = logging.getLogger(__name__)


class ConfigManager(object):
    """
    Config reader and parser helper.
    XML support
    """

    @staticmethod
    def parse_config(config):
        parsers = [
            ('xml', parse_xml),
            ('yaml', parse_yaml)
        ]
        for name, parser in parsers:
            try:
                return parser(config)
            except ParseError as exc:
                logger.warning("%s config parsing error: %s", name, exc)

        logger.warning("Couldn't parse monitoring config at %s. Using default config", config)
        return []

    @staticmethod
    def _apply_defaults(host_config, defaults: dict):
        if not defaults:
            return

        for k, v in defaults.items():
            if hasattr(host_config, k):
                if getattr(host_config, k) is None:
                    setattr(host_config, k, deepcopy(v))
            elif not host_config.get(k):
                host_config[k] = deepcopy(v)

    def getconfig(self, filename, target_hint, defaults: dict = None):
        """Prepare config data."""
        defaults = defaults or {}
        try:
            config = read_resource(filename)
        except IOError as exc:
            logger.error("Error loading config: %s", exc)
            raise RuntimeError("Can't read monitoring config %s" % filename)

        hosts = self.parse_config(config)
        config = []
        for host in hosts:
            host_config = self.get_host_config(host, target_hint)
            self._apply_defaults(host_config, defaults)
            config.append(host_config)
        return config

    def get_host_config(self, host, target_hint):
        defaults = {
            "cpu": {
                "name": '[inputs.cpu]',
                "percpu": 'false',
                "fielddrop": '["time_*", "usage_guest_nice"]'
            },
            "memory": {
                "name": '[inputs.mem]',
                "fielddrop":
                '["active", "inactive", "total", "used_per*", "avail*"]',
            },
            "disk": {
                "name": '[inputs.diskio]',
                "devices": '[{devices}]'.format(
                    devices=",".join(
                        ['"vda%s","sda%s"' % (num, num) for num in range(6)])),
            },
            "net": {
                "name": '[inputs.net]',
                "interfaces": '[{interfaces}]'.format(
                    interfaces=",".join(
                        ['"eth%s"' % (num) for num in range(6)])),
                "fielddrop":
                '["icmp*", "ip*", "udplite*", "tcp*", "udp*", "drop*", "err*"]',
            },
            "nstat": {
                "name": '[inputs.nstat]',
                "fieldpass": '["TcpRetransSegs"]',
            },
            "netstat": {
                "name": '[inputs.netstat]',
            },
            "netresponse": {
                "name": '[inputs.net_response]',
                "protocol": '"tcp"',
                "address": '":80"',
                "timeout": '"1s"'
            },
            "system": {
                "name": '[inputs.system]',
                "fielddrop": '["n_users", "n_cpus", "uptime*"]',
            },
            "kernel": {
                "name": '[inputs.kernel]',
                "fielddrop": '["boot_time"]',
            },
            "kernelvmstat": {
                "name": '[inputs.kernel_vmstat]',
                "fieldpass": '["pgfault", "pgmajfault"]',
            }
        }

        # compatibility with native telegraf metric names
        defaults['mem'] = defaults['memory']
        defaults['diskio'] = defaults['disk']
        defaults['net_response'] = defaults['netresponse']
        defaults['kernel_vmstat'] = defaults['kernelvmstat']

        defaults_enabled = ['cpu', 'memory', 'disk', 'net', 'system', 'kernel']
        defaults_boolean = [
            'percpu', 'round_interval', 'fielddrop', 'fieldpass', 'interfaces',
            'devices'
        ]
        hostname = host.address.lower()
        if hostname == TARGET_HINT_PLACEHOLDER:
            if not target_hint:
                raise ValueError(
                    f"Can't use `{TARGET_HINT_PLACEHOLDER}` keyword with no target parameter specified"
                )
            logger.debug("Using target hint: %s", target_hint)
            hostname = target_hint.lower()
        custom = []
        startups = []
        shutdowns = []
        sources = []
        telegrafraw = []
        # agent defaults
        host_config = CaseInsensitiveDict()
        for metric in host.metrics:
            metric_name = str(metric.name).lower()
            if metric_name in defaults:
                for key in tuple(defaults[metric_name].keys()):
                    if key != 'name' and key not in defaults_boolean:
                        value = metric.get(key, None)
                        if value:
                            defaults[metric_name][key] = "'{value}'".format(
                                value=value)
                    elif key in defaults_boolean:
                        value = metric.get(key, None)
                        if value:
                            defaults[metric_name][key] = "{value}".format(
                                value=value)
                host_config[metric_name] = defaults[metric_name]
            # custom metrics
            if metric_name == 'custom':
                isdiff = metric.get('diff', 0)
                cmd = {
                    'cmd': metric.text,
                    'label': metric.get('label'),
                    'diff': isdiff
                }
                custom.append(cmd)
            elif metric_name == 'startup':
                startups.append(metric.text)
            elif metric_name == 'shutdown':
                shutdowns.append(metric.text)
            elif metric_name == 'source':
                sources.append(metric.text)
            elif metric_name == 'telegrafraw':
                telegrafraw.append(metric.text)
        if len(host_config) == 0:
            logger.info('Empty host config, using defaults')
            for section in defaults_enabled:
                host_config[section] = defaults[section]
        result = {
            'host_config': host_config,
            'port': int(host.get('port', 22)),
            'python': host.get('python', '/usr/bin/env python3'),
            'interval': host.get('interval', 1),
            'username': host.get('username', getpass.getuser()),
            'telegraf': host.get('telegraf', '/usr/bin/telegraf'),
            'comment': host.get('comment', ''),
            'ssh_key_path': host.get('ssh_key_path'),
            'custom': custom,
            'host': hostname,
            'startup': startups,
            'shutdown': shutdowns,
            'source': sources,
            'telegrafraw': telegrafraw
        }
        logger.info("Telegraf Result config %s", result)
        return result


class AgentConfig(object):
    """ Agent config generator helper """

    def __init__(self, config, old_style_configs):
        self.host = config['host']
        self.custom = config['custom']
        self.startups = config['startup']
        self.shutdowns = config['shutdown']
        self.sources = config['source']
        self.interval = config['interval']
        self.comment = config['comment']
        self.telegrafraw = config['telegrafraw']
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
            config = configparser.RawConfigParser(strict=False)
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
            config.add_section('source')
            [
                config.set('source', "file%s" % idx, path)
                for idx, path in enumerate(self.sources)
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

        defaults_old_enabled = ['cpu', 'memory', 'disk', 'net', 'system']

        try:
            config = configparser.RawConfigParser(strict=False)

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
                    for key, value in self.host_config[section].items():
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
                        for key, value in self.host_config[section].items():
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

            # telegraf raw configuration into xml
            telegraf_raw = "".join(self.telegrafraw)

            with open(cfg_path, 'a') as fds:
                fds.write(telegraf_raw)

        except Exception as exc:
            logger.error(
                'Error trying to create monitoring config. Malformed? %s',
                exc,
                exc_info=True)
        return cfg_path


def create_agent_py(agent_filename):
    with open(agent_filename, 'w') as f:
        f.write(read_resource(pkg_resources.resource_filename('yandextank.plugins.Telegraf', 'agent/agent.py')))
    os.chmod(agent_filename, 0o775)
    return os.path.abspath(agent_filename)
