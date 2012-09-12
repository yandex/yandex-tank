from Tank.Core import AbstractPlugin
import logging
import time

class DummyPlugin(AbstractPlugin):
    def __init__(self, core):
        #super(AbstractPlugin, self).__init__(core)
        self.log = logging.getLogger(__name__)
        self.count = 0
        
    @staticmethod
    def get_key():
        return __file__;
    
    def configure(self):
        self.log.debug("Configure2")
    def prepare_test(self):
        self.log.debug("Prepare2")
    def start_test(self):
        self.log.debug("Start2")
        time.sleep(1)
    def end_test(self, rc):
        self.log.debug("End2")
        
    def is_test_finished(self):
        self.count += 1
        if self.count > 3:
            return 0
        else:
            self.log.debug("Delaying")
            time.sleep(0.2)
            return -1
        
