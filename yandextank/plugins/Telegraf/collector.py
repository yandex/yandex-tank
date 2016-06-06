"""Monitoring collector """
import logging
import time
import sys
import json

from ...core.interfaces import MonitoringDataListener
from ..Telegraf.client import SSHClient, LocalhostClient
from ..Telegraf.config import ConfigManager

logger = logging.getLogger(__name__)


class MonitoringCollector(object):
    """Aggregate data from several collectors"""

    def __init__(self):
        self.config = None
        self.default_target = None
        self.agents = []
        self.agent_sessions = []
        self.listeners = []
        self.first_data_received = False
        self.send_data = []
        self.artifact_files = []
        self.inputs, self.outputs, self.excepts = [], [], []
        self.load_start_time = None
        self.config_manager = ConfigManager()

    def add_listener(self, obj):
        self.listeners.append(obj)

    def prepare(self):
        """Prepare for monitoring - install agents etc"""

        # Parse config
        agent_configs = []
        if self.config:
            agent_configs = self.config_manager.getconfig(self.config, self.default_target)

        # Creating agent for hosts
        logger.debug('Creating agents')
        for config in agent_configs:
            if config['host'] == "localhost" or config['host'] == "127.0.0.1" or config['host'] == '::1':
                logger.debug('Creating LocalhostClient for host %s', config['host'])
                client =  LocalhostClient(config)
            else:
                logger.debug('Creating SSHClient for host %s', config['host'])
                client = SSHClient(config, timeout=5)
            logger.debug('Installing monitoring agent. Host: %s', client.host)
            agent_config, startup_config = client.install()
            if agent_config:
                self.agents.append(client)
                self.artifact_files.append(agent_config)
            if startup_config:
                self.artifact_files.append(startup_config)

    def start(self):
        """Start agents"""
        [agent.start() for agent in self.agents]
        [agent.reader_thread.start() for agent in self.agents]

    def poll(self):
        """Poll agents for data
        """
        start_time = time.time()
        for agent in self.agents:
            for collect in agent.reader:
                for chunk in collect:
                    ts, prepared_results = chunk
                    ready_to_send_json = json.dumps([
                        {
                            "timestamp": ts,
                            "data": {
                                agent.host: {
                                    "comment": "test",
                                    "metrics": prepared_results
                                }
                            }
                        }
                    ])
                    self.send_data.append(ready_to_send_json+'\n')

        logger.debug('Polling/decoding agents data took: %.2fms', (time.time() - start_time) * 1000)

        if not self.first_data_received and self.send_data:
            self.first_data_received = True
            logger.info("Monitoring received first data.")
        else:
            self.send_collected_data()
        return len(self.outputs)

    def stop(self):
        """Shutdown agents"""
        logger.debug("Uninstalling monitoring agents")
        for agent in self.agents:
            log_filename, data_filename = agent.uninstall()
            self.artifact_files.append(log_filename)
            self.artifact_files.append(data_filename)

    def send_collected_data(self):
        """sends pending data set to listeners"""
        [listener.monitoring_data(self.send_data) for listener in self.listeners]
        self.send_data = []


class StdOutPrintMon(MonitoringDataListener):
    """Simple listener, writing data to stdout"""

    def __init__(self):
        MonitoringDataListener.__init__(self)

    def monitoring_data(self, data_string):
        [sys.stdout.write(chunk) for chunk in data_string]

