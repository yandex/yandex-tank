from Tank.Core import AbstractPlugin
import os
import subprocess
import signal
from Tank import Utils

# TODO: make it work with all other plugins

class JMeterPlugin(AbstractPlugin):
    SECTION = 'jmeter'
    
    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.jmeter_process = None
        self.args = None

    @staticmethod
    def get_key():
        return __file__;
    
    def configure(self):
        self.jmx = self.get_option("jmx")
        self.log.debug("JMX: %s", os.path.realpath(self.jmx))
        self.user_args = self.get_option("args", '')
        self.jmeter_path = self.get_option("jmeter_path", 'jmeter')
        self.jmeter_log = self.get_option("jmeter_log", 'jmeter.log')

    def prepare_test(self):
        self.args = [self.jmeter_path, "-n", "-t", self.jmx, '-j', self.jmeter_log]
        self.args += Utils.splitstring(self.user_args)
            
    def start_test(self):
        self.log.debug("Starting %s with arguments: %s", self.jmeter_path, self.args)
        self.jmeter_process = subprocess.Popen(self.args, executable=self.jmeter_path, stderr=subprocess.PIPE, stdout=subprocess.PIPE, preexec_fn=os.setsid)
    
    def is_test_finished(self):
        rc = self.jmeter_process.poll()
        if rc != None:
            self.log.debug("JMeter RC %s", rc)
            return rc
        else:
            return -1
        
    def end_test(self, retcode):
        if self.jmeter_process.poll() == None:
            self.log.warn("Terminating jmeter process with PID %s", self.jmeter_process.pid)
            self.jmeter_process.terminate()
            os.killpg(self.jmeter_process.pid, signal.SIGTERM)
        else:
            self.log.debug("Seems JMeter finished OK")
        
        Utils.log_stdout_stderr(self.log, self.jmeter_process.stdout, self.jmeter_process.stderr, "jmeter")

        self.core.add_artifact_file(self.jmeter_log)
        return retcode
            
