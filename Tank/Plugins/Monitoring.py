from Tank.Core import AbstractPlugin
from Tank.Plugins.DataUploader import DataUploaderPlugin
from Tank.Plugins.Phantom import PhantomPlugin
import os
import tempfile
from MonCollector.collector import MonitoringCollector, MonitoringDataListener
from Tank.Plugins.ConsoleOnline import ConsoleOnlinePlugin, AbstractInfoWidget

# TODO: wait for first monitoring data
class MonitoringPlugin(AbstractPlugin):
    SECTION = 'monitoring'
    
    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.jobno = None
        self.default_target = None
        self.config = None
        self.process = None
        self.monitoring = None

    @staticmethod
    def get_key():
        return __file__;
    
    def configure(self):
        self.config = self.get_option("config", 'auto')
    
    def prepare_test(self):
        phantom = None
        try:
            phantom = self.core.get_plugin_of_type(PhantomPlugin)
        except KeyError, ex:
            self.log.debug("Phantom plugin not found: %s", ex)
        if phantom:
            self.default_target = phantom.address
            # TODO: resolve virtual to host address
        
        if self.config == 'auto':
            self.config = os.path.dirname(__file__) + '/monitoring_default_config.xml'

        self.core.add_artifact_file(self.config, True)
        

        if not self.config or self.config == 'none':
            self.log.info("Monitoring has been disabled")
        else:
            self.log.info("Starting monitoring with config: %s", self.config)
            self.monitoring = MonitoringCollector(self.config)
            if self.default_target:
                self.monitoring.default_target = self.default_target
            
            data_file = tempfile.mkstemp('.data', 'monitoring_')[1]
            self.monitoring.add_listener(SaveMonToFile(data_file))
            self.core.add_artifact_file(data_file)

            try:
                console = self.core.get_plugin_of_type(ConsoleOnlinePlugin)
            except Exception, ex:
                self.log.debug("Console not found: %s", ex)
                console = None
            if console:    
                console.add_info_widget(MonitoringWidget(self))

            try:
                uploader = self.core.get_plugin_of_type(DataUploaderPlugin)
            except KeyError, ex:
                self.log.debug("Uploader plugin not found: %s", ex)
                uploader = None
            if uploader:
                self.monitoring.add_listener(uploader)
    
            self.monitoring.prepare()
            
    def start_test(self):
        if self.monitoring:
            self.monitoring.start()
            
    def is_test_finished(self):
        if self.monitoring and not self.monitoring.poll():
            # FIXME: don't interrupt test if we have default config
            if self.config and self.config != 'none':
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
        return retcode
    

class SaveMonToFile(MonitoringDataListener):
    def __init__(self, out_file):
        if out_file:
            self.store = open(out_file, 'w')
    
    def monitoring_data(self, data_string):
            self.store.write(data_string)
            self.store.flush()


# TODO: add widget with current metrics
class MonitoringWidget(AbstractInfoWidget, MonitoringDataListener):
    def get_index(self):
        return 50

    def monitoring_data(self, data_string):
        self.log.debug("Mon data: %s", data_string)
    
    def render(self, screen):
        return AbstractInfoWidget.render(self, screen)
