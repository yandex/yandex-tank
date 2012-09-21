from Tank.MonCollector.collector import MonitoringCollector, MonitoringDataListener
from Tank.Core import AbstractPlugin
from Tank.Plugins.ConsoleOnline import ConsoleOnlinePlugin, AbstractInfoWidget
from Tank.Plugins.Phantom import PhantomPlugin
import base64
import copy
import os
import tempfile
import time

class MonitoringPlugin(AbstractPlugin):
    SECTION = 'monitoring'
    
    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.jobno = None
        self.default_target = None
        self.config = None
        self.process = None
        self.monitoring = MonitoringCollector()
        self.die_on_fail = True

    @staticmethod
    def get_key():
        return __file__;
    
    def configure(self):
        self.config = self.get_option("config", 'auto')
        if self.config == 'auto':
            self.config = os.path.dirname(__file__) + '/monitoring_default_config.xml'
        self.core.add_artifact_file(self.config, True)
        
        if self.config == 'none' or self.config == 'auto':
            self.die_on_fail = False         
            
        if self.config == 'none':
            self.monitoring = None
    
    def prepare_test(self):
        phantom = None
        try:
            phantom = self.core.get_plugin_of_type(PhantomPlugin)
        except KeyError, ex:
            self.log.debug("Phantom plugin not found: %s", ex)
        if phantom:
            self.default_target = phantom.address
            if phantom.phout_import_mode:
                self.config=None
            # TODO: 2 resolve virtual to host address
        
        if not self.config or self.config == 'none':
            self.log.info("Monitoring has been disabled")
        else:
            self.log.info("Starting monitoring with config: %s", self.config)
            self.monitoring.config = self.config
            if self.default_target:
                self.monitoring.default_target = self.default_target
            
            data_file = tempfile.mkstemp('.data', 'monitoring_', self.core.artifacts_base_dir)[1]
            self.monitoring.add_listener(SaveMonToFile(data_file))
            self.core.add_artifact_file(data_file)

            try:
                console = self.core.get_plugin_of_type(ConsoleOnlinePlugin)
            except Exception, ex:
                self.log.debug("Console not found: %s", ex)
                console = None
            if console:    
                widget = MonitoringWidget(self)
                console.add_info_widget(widget)
                self.monitoring.add_listener(widget)

            self.monitoring.prepare()
            self.monitoring.start()
            while not self.monitoring.first_data_received:
                time.sleep(0.2)
                self.monitoring.poll()
            
    def is_test_finished(self):
        if self.monitoring and not self.monitoring.poll():
            if self.die_on_fail:
                raise RuntimeError("Monitoring died unexpectedly")
            else:
                self.log.warn("Monitoring died unexpectedly")
                self.monitoring = None
        else:
            return -1
            
            
    def end_test(self, retcode):
        self.log.info("Finishing monitoring")
        if self.monitoring:
            self.monitoring.stop()
            for log in self.monitoring.artifact_files:
                self.core.add_artifact_file(log)
        return retcode
    

class SaveMonToFile(MonitoringDataListener):
    def __init__(self, out_file):
        if out_file:
            self.store = open(out_file, 'w')
    
    def monitoring_data(self, data_string):
            self.store.write(data_string)
            self.store.flush()


class MonitoringWidget(AbstractInfoWidget, MonitoringDataListener):

    NA = 'n/a'
    def __init__(self, owner):
        AbstractInfoWidget.__init__(self)
        self.owner = owner
        self.data = {}
        self.metrics = {}
        self.sign = {}
        self.max_metric_len = 0
    
    def get_index(self):
        return 50

    def monitoring_data(self, data_string):
        self.log.debug("Mon widget data: %s", data_string)
        for line in data_string.split("\n"):
            if not line.strip():
                continue
            data = line.strip().split(';')
            if data[0] == 'start':
                data.pop(0) # remove 'start'
                host = data.pop(0)
                if not data:
                    continue;
                data.pop(0) # remove timestamp
                self.metrics[host] = []
                self.data[host] = {}
                self.sign[host] = {}
                for metric in data:
                    if metric.startswith("Custom:"):
                        metric = base64.standard_b64decode(metric.split(':')[1])
                    self.metrics[host].append(metric)
                    self.max_metric_len = max(self.max_metric_len, len(metric))                    
                    self.data[host][metric] = self.NA
                    self.sign[host][metric] = 0
            else:
                host = data.pop(0)
                data.pop(0) # remove timestamp
                metrics = copy.copy(self.metrics[host])
                for value in data:
                    metric = metrics.pop(0)
                    if value == '':
                        value = self.NA
                        self.sign[host][metric] = -1
                        self.data[host][metric] = value
                    else:
                        if self.data[host][metric] == self.NA:
                            self.sign[host][metric] = 1
                        else:
                            if float(value) > float(self.data[host][metric]):
                                self.sign[host][metric] = 1
                            elif float(value) < float(self.data[host][metric]):
                                self.sign[host][metric] = -1
                            else:
                                self.sign[host][metric] = 0
                        self.data[host][metric] = "%.2f" % float(value) 
                
    
    def render(self, screen):
        if not self.owner.monitoring:
            return "Monitoring is " + screen.markup.RED + "offline" + screen.markup.RESET
        else:
            res = "Monitoring is " + screen.markup.WHITE + "online" + screen.markup.RESET + ":\n"
            for hostname, metrics in self.data.items():
                res += ("   " + screen.markup.CYAN + "%s" + screen.markup.RESET + ":\n") % hostname
                for metric, value in sorted(metrics.iteritems()):
                    if self.sign[hostname][metric] > 0:
                        value = screen.markup.GREEN + value + screen.markup.RESET
                    elif self.sign[hostname][metric] < 0:
                        value = screen.markup.RED + value + screen.markup.RESET
                    res += "      %s%s: %s\n" % (' ' * (self.max_metric_len - len(metric)), metric.replace('_', ' '), value)
                    
            return res.strip()
            
