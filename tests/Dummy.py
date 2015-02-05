from yandextank.core import AbstractPlugin
import time

class DummyPlugin(AbstractPlugin):
    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.count = 0
        
    @staticmethod
    def get_key():
        return __file__
    
    def configure(self):
        self.log.warn("Configure")
    
    def prepare_test(self):
        self.log.warn("Prepare")
    
    def start_test(self):
        self.log.warn("Start")

    def is_test_finished(self):
        self.count += 1
        if self.count > 3:
            self.log.warn("Triggering exit")
            return 0
        else:
            self.log.warn("Delaying")
            time.sleep(0.2)
            return -1
        
    def end_test(self, retcode):
        self.log.warn("End")
        
    def post_process(self, retcode):
        self.log.warn("Post-process")
