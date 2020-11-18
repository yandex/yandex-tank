"""Monitoring collector """
import hashlib
import logging
import sys
import time
from ...common.interfaces import MonitoringDataListener

from ..Telegraf.client import SSHClient, LocalhostClient
from ..Telegraf.config import ConfigManager

logger = logging.getLogger(__name__)


class MonitoringCollector(object):
    """Aggregate data from several collectors

    Workflow:
    plugin creates collector
    collector reads monitoring config and creates agents
    collector creates configs for agents (telegraf, shutdown&startup, custom scripts)
    collector installs agents on targets, send configs on targets
    agent starts startups on target, then starts telegraf
    agent reads output of telegraf, consolidates output, caches 5 seconds and then sends output to collector
    collector polls agents for data, decodes known metrics and counts diffs for diff-like metrics
    collector sends data to listeners

    """

    def __init__(self, disguise_hostnames, kill_old):
        self.kill_old = kill_old
        self.disguise_hostnames = disguise_hostnames
        self.config = None
        self.default_target = None
        self.agents = []
        self.agent_sessions = []
        self.listeners = []
        self.first_data_received = False
        self.__collected_data = []
        self.artifact_files = []
        self.load_start_time = None
        self.config_manager = ConfigManager()
        self.old_style_configs = False
        self.clients = {'localhost': LocalhostClient, 'ssh': SSHClient}

    def add_listener(self, obj):
        self.listeners.append(obj)

    def prepare(self):
        """Prepare for monitoring - install agents etc"""

        # Parse config
        agent_configs = []
        if self.config:
            agent_configs = self.config_manager.getconfig(
                self.config, self.default_target)

        # Creating agent for hosts
        for config in agent_configs:
            if config['host'] in ['localhost', '127.0.0.1', '::1']:
                client = self.clients['localhost'](
                    config, self.old_style_configs, kill_old=self.kill_old)
            else:
                client = self.clients['ssh'](
                    config, self.old_style_configs, timeout=5, kill_old=self.kill_old)
            logger.debug('Installing monitoring agent. Host: %s', client.host)
            agent_config, startup_config, customs_script = client.install()
            if agent_config:
                self.agents.append(client)
                self.artifact_files.append(agent_config)
            if startup_config:
                self.artifact_files.append(startup_config)
            if customs_script:
                self.artifact_files.append(customs_script)

    def start(self):
        """ Start agents

        execute popen of agent.py on target and start output reader thread.
        """
        [agent.start() for agent in self.agents]
        [agent.reader_thread.start() for agent in self.agents]

    def poll(self):
        """ Poll agents for data
        """
        start_time = time.time()
        for agent in self.agents:
            for collect in agent.reader:
                # don't crash if trash or traceback came from agent to stdout
                if not collect:
                    return 0
                for chunk in collect:
                    ts, prepared_results = chunk
                    if not self.first_data_received and prepared_results:
                        self.first_data_received = True
                        logger.info("Monitoring received first data.")
                    if self.load_start_time and int(
                            ts) >= self.load_start_time:
                        ready_to_send = {
                            "timestamp": int(ts),
                            "data": {
                                self.hash_hostname(agent.host): {
                                    "comment": agent.config.comment,
                                    "metrics": prepared_results
                                }
                            }
                        }
                        self.__collected_data.append(ready_to_send)

        logger.debug(
            'Polling/decoding agents data took: %.2fms',
            (time.time() - start_time) * 1000)

        data = self.__collected_data
        self.__collected_data = []
        return data

    def stop(self):
        """Shutdown agents"""
        logger.debug("Uninstalling monitoring agents")
        for agent in self.agents:
            agent._stop_agent()
        for agent in self.agents:
            try:
                log_filename, data_filename = agent.uninstall()
                self.artifact_files.append(log_filename)
                self.artifact_files.append(data_filename)
            except Exception as exc:
                logger.warning("Error while uninstalling agent %s", exc, exc_info=True)
        for agent in self.agents:
            try:
                logger.debug(
                    'Waiting for agent %s reader thread to finish.', agent)
                agent.reader_thread.join(10)
                self.agents.remove(agent)
            except BaseException:
                logger.error('Monitoring reader thread stuck!', exc_info=True)

    def get_rest_data(self):
        return self.__collected_data

    def hash_hostname(self, host):
        if self.disguise_hostnames and host:
            return hashlib.md5(host.encode()).hexdigest()
        else:
            return host


class StdOutPrintMon(MonitoringDataListener):
    """Simple listener, writing data to stdout"""

    def __init__(self):
        MonitoringDataListener.__init__(self)

    def monitoring_data(self, data_list):
        [sys.stdout.write(data) for data in data_list]
