''' Module to check system resources at load generator'''

from tankcore import AbstractPlugin
import tankcore
import time

class ResourceCheckPlugin(AbstractPlugin):
    '''   Plugin to check system resources    '''
    SECTION = "rcheck"
    
    @staticmethod
    def get_key():
        return __file__
    

    def __init__(self, core):
        '''         Constructor        '''
        AbstractPlugin.__init__(self, core)
        self.interval = "10s"
        self.disk_limit = 2048 # 2 GB
        self.mem_limit = 512 # 0.5 GB
        self.last_check = 0

    def configure(self):
        self.interval = tankcore.expand_to_seconds(self.get_option("interval", self.interval))
        self.disk_limit = int(self.get_option("disk_limit", self.disk_limit))
        self.mem_limit = int(self.get_option("mem_limit", self.mem_limit))
        
    def prepare_test(self):
        self.__check_disk()
        self.__check_mem()
        
    def is_test_finished(self):
        if time.time() - self.last_check < self.interval:
            return -1
        self.__check_disk()
        self.__check_mem()
        self.last_check = time.time()
        return -1


    def __check_disk(self):
        ''' raise exception on disk space exceeded '''
        cmd = "df --no-sync -m -P -l -x fuse -x tmpfs -x devtmpfs "
        cmd += self.core.artifacts_base_dir
        cmd += " | tail -n 1 | awk '{print $4}'"
        disk_free = tankcore.execute(cmd, True, 0.1, True)[1]
        self.log.debug("Disk free space: %s/%s", disk_free.strip(), self.disk_limit)
        if int(disk_free.strip()) < self.disk_limit:
            raise RuntimeError("Not enough local resources: disk space less than %sMB in %s: %sMB" % (self.disk_limit, self.core.artifacts_base_dir, int(disk_free.strip()))) 

        
    def __check_mem(self):
        ''' raise exception on RAM exceeded '''
        cmd = "free -m | awk '$1==\"-/+\" {print $4}'"
        mem_free = int(tankcore.execute(cmd, True, 0.1, True)[1].strip())
        self.log.debug("Memory free: %s/%s", mem_free, self.mem_limit)
        if mem_free < self.mem_limit:
            raise RuntimeError("Not enough resources: free memory less than %sMB: %sMB" % (self.mem_limit, mem_free)) 
    
    
    
