'''
Module to provide target monitoring
'''

from Tank.MonCollector.collector import MonitoringCollector, \
    MonitoringDataListener
from Tank.Plugins.ConsoleOnline import ConsoleOnlinePlugin, AbstractInfoWidget
from Tank.Plugins.Phantom import PhantomPlugin
from tankcore import AbstractPlugin
import base64
import copy
import os
import time
import traceback

class MonitoringPlugin(AbstractPlugin):
    '''
    Tank plugin
    '''
    
    SECTION = 'monitoring'
    
    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.jobno = None
        self.default_target = None
        self.config = None
        self.process = None
        self.monitoring = MonitoringCollector()
        self.die_on_fail = True
        self.data_file = None
        self.mon_saver = None

    @staticmethod
    def get_key():
        return __file__
    
    def configure(self):
        self.config = self.get_option("config", 'auto')
        self.default_target = self.get_option("default_target", 'localhost')

        if self.config == 'none' or self.config == 'auto':
            self.die_on_fail = False
        else:
            if not os.path.exists(self.config):
                raise OSError("Monitoring config file not found: %s" % self.config)         
                    
        if self.config == 'none':
            self.monitoring = None
    
        if self.config == 'auto':
            self.config = os.path.dirname(__file__) + '/monitoring_default_config.xml'
        
    def prepare_test(self):
        phantom = None
        try:
            phantom = self.core.get_plugin_of_type(PhantomPlugin)
        except KeyError, ex:
            self.log.debug("Phantom plugin not found: %s", ex)
        if phantom:
            if phantom.phantom:
                self.default_target = phantom.phantom.address
            if phantom.phout_import_mode:
                self.config = None
            # TODO: 2 resolve virtual to host address

        
        if not self.config or self.config == 'none':
            self.log.info("Monitoring has been disabled")
        else:
            self.log.info("Starting monitoring with config: %s", self.config)
            self.core.add_artifact_file(self.config, True)
            self.monitoring.config = self.config
            if self.default_target:
                self.monitoring.default_target = self.default_target
            
            self.data_file = self.core.mkstemp('.data', 'monitoring_')
            self.mon_saver = SaveMonToFile(self.data_file)
            self.monitoring.add_listener(self.mon_saver)
            self.core.add_artifact_file(self.data_file)

            try:
                console = self.core.get_plugin_of_type(ConsoleOnlinePlugin)
            except Exception, ex:
                self.log.debug("Console not found: %s", ex)
                console = None
            if console:    
                widget = MonitoringWidget(self)
                console.add_info_widget(widget)
                self.monitoring.add_listener(widget)

            try:
                self.monitoring.prepare()
                self.monitoring.start()
                count = 0
                while not self.monitoring.first_data_received and count < 15 * 5:
                    time.sleep(0.2)
                    self.monitoring.poll()
                    count += 1
            except Exception, exc:
                self.log.debug("Problems starting monitoring: %s", traceback.format_exc(exc))
                if self.die_on_fail:
                    raise exc
                else:
                    self.log.warning("Failed to start monitoring: %s", exc)
                    self.monitoring = None
            
    def is_test_finished(self):
        if self.monitoring and not self.monitoring.poll():
            if self.die_on_fail:
                raise RuntimeError("Monitoring died unexpectedly")
            else:
                self.log.warn("Monitoring died unexpectedly")
                self.monitoring = None
        return -1
            
            
    def end_test(self, retcode):
        self.log.info("Finishing monitoring")
        if self.monitoring:
            self.monitoring.stop()
            for log in self.monitoring.artifact_files:
                self.core.add_artifact_file(log)
        
        if self.mon_saver:
            self.mon_saver.close()
        return retcode
    

class SaveMonToFile(MonitoringDataListener):
    '''
    Default listener - saves data to file
    '''
    def __init__(self, out_file):
        if out_file:
            self.store = open(out_file, 'w')
    
    def monitoring_data(self, data_string):
        self.store.write(data_string)
        self.store.flush()
    
    def close(self):
        if self.store:
            self.store.close()


class MonitoringDataDecoder:
    '''
    The class that serves converting monitoring data lines to dict
    '''
    NA = 'n/a'

    def __init__(self):
        self.metrics = {}
    
    def decode_line(self, line):
        is_initial = False
        data_dict = {}
        data = line.strip().split(';')
        if data[0] == 'start':
            data.pop(0) # remove 'start'
            host = data.pop(0)
            if not data:
                raise ValueError("Wrong mon data line: %s", line)
            
            data.pop(0) # remove timestamp
            self.metrics[host] = []
            for metric in data:
                if metric.startswith("Custom:"):
                    metric = base64.standard_b64decode(metric.split(':')[1])
                self.metrics[host].append(metric)
                data_dict[metric] = self.NA
                is_initial = True
        else:
            host = data.pop(0)
            data.pop(0) # remove timestamp
            for metric in self.metrics[host]:
                data_dict[metric] = data.pop(0)
        return host, data_dict, is_initial

            
class MonitoringWidget(AbstractInfoWidget, MonitoringDataListener, MonitoringDataDecoder):
    '''
    Screen widget
    '''

    def __init__(self, owner):
        AbstractInfoWidget.__init__(self)
        MonitoringDataDecoder.__init__(self)
        self.owner = owner
        self.data = {}
        self.sign = {}
        self.max_metric_len = 0
    
    def get_index(self):
        return 50
    
    def handle_data_item(self, host, data):
        for metric, value in data.iteritems():
            if value == '' or value == self.NA:
                value = self.NA
                self.sign[host][metric] = -1
                self.data[host][metric] = value
            else:
                if self.data[host][metric] == self.NA:
                    self.sign[host][metric] = 1
                elif float(value) > float(self.data[host][metric]):
                    self.sign[host][metric] = 1
                elif float(value) < float(self.data[host][metric]):
                    self.sign[host][metric] = -1
                else:
                    self.sign[host][metric] = 0
                self.data[host][metric] = "%.2f" % float(value)


    def monitoring_data(self, data_string):
        self.log.debug("Mon widget data: %s", data_string)
        for line in data_string.split("\n"):
            if not line.strip():
                continue
            
            host, data, initial = self.decode_line(line)
            if initial:
                self.sign[host] = {}
                self.data[host] = {}
                for metric in data.keys():
                    self.sign[host][metric] = 0
                    self.data[host][metric] = self.NA
            else:
                self.handle_data_item(host, data) 
                
    
    def render(self, screen):
        if not self.owner.monitoring:
            return "Monitoring is " + screen.markup.RED + "offline" + screen.markup.RESET
        else:
            res = "Monitoring is " + screen.markup.WHITE + "online" + screen.markup.RESET + ":\n"
            for hostname, metrics in self.data.items():
                res += ("   " + screen.markup.CYAN + "%s" + screen.markup.RESET + ":\n") % hostname
                for metric, value in sorted(metrics.iteritems()):
                    if self.sign[hostname][metric] > 0:
                        value = screen.markup.YELLOW + value + screen.markup.RESET
                    elif self.sign[hostname][metric] < 0:
                        value = screen.markup.CYAN + value + screen.markup.RESET
                    res += "      %s%s: %s\n" % (' ' * (self.max_metric_len - len(metric)), metric.replace('_', ' '), value)
                    
            return res.strip()
            

# TODO: 3 add autostop criteria on metric
