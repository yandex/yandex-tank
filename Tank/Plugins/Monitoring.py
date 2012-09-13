from Tank import Utils
from Tank.Core import AbstractPlugin
from Tank.Plugins.DataUploader import DataUploaderPlugin
from Tank.Plugins.Phantom import PhantomPlugin
import os
import signal
import subprocess
import tempfile

# TODO: wait for first monitoring data
class MonitoringPlugin(AbstractPlugin):
    SECTION = 'monitoring'
    
    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.jobno = None
        self.default_target = None
        self.config = None
        self.process = None

    @staticmethod
    def get_key():
        return __file__;
    
    def configure(self):
        self.data_file = tempfile.mkstemp('.data', 'monitoring_')[1]
        self.core.add_artifact_file(self.data_file)
        self.config = self.get_option("config", '')
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
        
        if not self.config:
            self.config = os.path.dirname(__file__) + '/monitoring_default_config.xml'

        self.core.add_artifact_file(self.config, True)
            
    # TODO: add unit tests: disabled, default, and set config            
    def start_test(self):
        # TODO: change subprocess to direct object manipulation
        if self.config=='none':
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
            args = ["load-monitor", "--config=" + self.config, "--output=" + self.data_file]
            if self.jobno:
                args += ["-j", str(self.jobno)]
            if self.default_target:
                args += ["-t", self.default_target]
            self.log.debug("Starting: %s", args)
            self.process = subprocess.Popen(args, preexec_fn=os.setsid, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

    def is_test_finished(self):
        rc = self.process.poll()
        if rc != None:
            # FIXME: don't interrupt test if we have default config
            self.log.error("Monitoring died unexpectedly with RC: %s", rc)
            return rc
        else:
            return -1
            
            
    def end_test(self, retcode):
        if self.process and self.process.poll() == None:
            self.log.debug("Terminating monitoring process with PID %s", self.process.pid)
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.terminate()
            except Exception, ex:
                self.log.warning("Failed to kill monitoring process with pid %s: %s", self.process.pid, ex)
        else:
            self.log.warn("Seems the monitoring has been finished")

        if self.process:
            Utils.log_stdout_stderr(self.log, self.process.stdout, None, self.SECTION)
            Utils.log_stdout_stderr(self.log, self.process.stderr, None, self.SECTION + " err")

        return retcode
    
# TODO: add widget with current metrics
