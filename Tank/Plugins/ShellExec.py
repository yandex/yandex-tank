from Tank.Core import AbstractPlugin
from Tank.Utils import CommonUtils
import logging

class ShellExecPlugin(AbstractPlugin):
    SECTION = 'shellexec'
    
    def __init__(self, core):
        self.log = logging.getLogger(__name__)
        self.core = core
        self.end = None
        self.poll = None
        self.prepare = None
        self.start = None
        self.postprocess = None

    @staticmethod
    def get_key():
        return __file__
    
    def configure(self):
        self.prepare = self.core.get_option(self.SECTION, "prepare", '')
        self.start = self.core.get_option(self.SECTION, "start", '')
        self.end = self.core.get_option(self.SECTION, "end", '')
        self.poll = self.core.get_option(self.SECTION, "poll", '')
        self.postprocess = self.core.get_option(self.SECTION, "post_process", '')

    def prepare_test(self):
        if self.prepare:
            self.execute(self.prepare)
            
            
    def start_test(self):
        if self.start:
            self.execute(self.start)

    def is_test_finished(self):
        if self.poll:
            self.execute(self.poll)
            
    def end_test(self, rc):
        if self.end:
            self.execute(self.end)
        return rc

    def post_process(self, rc):
        if self.postprocess:
            self.execute(self.postprocess)
        return rc

    def execute(self, cmd):
        rc = CommonUtils.execute(cmd, shell=True, poll_period=0.1)
        if rc:
            raise RuntimeError("Subprocess returned %s",)    
