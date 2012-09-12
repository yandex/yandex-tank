from Tank.Core import AbstractPlugin
import logging
import os
import subprocess
from Tank.Utils import CommonUtils

# TODO: make it work with all other plugins

class JMeterPlugin(AbstractPlugin):
    SECTION = 'jmeter'
    
    def __init__(self, core):
        self.log = logging.getLogger(__name__)
        self.core = core
        self.jmeter_process = None
        self.args = None

    @staticmethod
    def get_key():
        return __file__;
    
    def configure(self):
        self.jmx = self.core.get_option(self.SECTION, "jmx")
        self.log.debug("JMX: %s", os.path.realpath(self.jmx))
        self.user_args = self.core.get_option(self.SECTION, "args", '')
        self.jmeter_path = self.core.get_option(self.SECTION, "jmeter_path", 'jmeter')
        self.jmeter_log = self.core.get_option(self.SECTION, "jmeter_log", 'jmeter.log')

    def prepare_test(self):
        self.args = [self.jmeter_path, "-n", "-t", self.jmx, '-j', self.jmeter_log]
        self.args += self.splitstring(self.user_args)
            
    def start_test(self):
        self.log.debug("Starting %s with arguments: %s", self.jmeter_path, self.args)
        self.jmeter_process = subprocess.Popen(self.args, executable=self.jmeter_path, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    
    def end_test(self, rc):
        if self.jmeter_process.poll() == None:
            self.log.warn("Terminating jmeter process with PID %s", self.jmeter_process.pid)
            self.jmeter_process.terminate()
            # FIXME: we have a problem here, the JMeter process isn't dead
            #import signal
            #os.killpg(self.jmeter_process.pid, signal.SIGTERM)
            #pkill -P
        else:
            self.log.debug("Seems JMeter finished OK")
        
        self.core.add_artifact_file(self.jmeter_log)
        return rc
            
    def is_test_finished(self):
        CommonUtils.log_stdout_stderr(self.log, self.jmeter_process.stdout, self.jmeter_process.stderr, "jmeter")

        rc = self.jmeter_process.poll()
        if rc != None:
            self.log.debug("JMeter RC %s", rc)
            return rc
        else:
            return -1
        
    def splitstring(self, string):
        """
        >>> string = 'apple orange "banana tree" green'
        >>> splitstring(string)
        ['apple', 'orange', 'green', '"banana tree"']
        """
        import re
        p = re.compile(r'"[\w ]+"')
        if p.search(string):
            quoted_item = p.search(string).group()
            newstring = p.sub('', string)
            return newstring.split() + [quoted_item]
        else:
            return string.split()
