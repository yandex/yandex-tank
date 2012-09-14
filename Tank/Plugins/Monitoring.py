from Tank.Core import AbstractPlugin
from Tank.Plugins.DataUploader import DataUploaderPlugin
from Tank.Plugins.Phantom import PhantomPlugin
import os
import tempfile
from MonCollector.collector import MonitoringCollector

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
        self.data_file = tempfile.mkstemp('.data', 'monitoring_')[1]
        self.core.add_artifact_file(self.data_file)
        self.config = self.get_option("config", 'auto')
        self.core.add_artifact_file("monitoring.log")
    
    def prepare_test(self):
        phantom = None
        try:
            phantom = self.core.get_plugin_of_type(PhantomPlugin)
        except KeyError, ex:
            self.log.debug("Phantom plugin not found: %s", ex)
        if phantom:
            self.default_target = phantom.address
            # TODO: resolve virtual to host address
        
        if self.config=='auto':
            self.config = os.path.dirname(__file__) + '/monitoring_default_config.xml'

        self.core.add_artifact_file(self.config, True)
            
    def start_test(self):
        if not self.config or self.config == 'none':
            self.log.info("Monitoring has been disabled")
        else:
            uploader = None
            try:
                uploader = self.core.get_plugin_of_type(DataUploaderPlugin)
            except KeyError, ex:
                self.log.debug("Uploader plugin not found: %s", ex)
            if uploader:
                self.jobno = uploader.jobno
    
            self.log.info("Starting monitoring with config: %s", self.config)
            self.monitoring = MonitoringCollector(self.config, self.data_file)
            if self.jobno:
                self.monitoring.jobno = self.jobno
            if self.default_target:
                self.monitoring.default_target = self.default_target
            self.monitoring.start()

    def is_test_finished(self):
        if self.monitoring and not self.monitoring.poll():
            # FIXME: don't interrupt test if we have default config
            raise RuntimeError("Monitoring died unexpectedly")
        else:
            return -1
            
            
    def end_test(self, retcode):
        self.log.info("Finishing monitoring")
        if self.monitoring:
            self.monitoring.stop()
        return retcode
    
# TODO: add widget with current metrics
