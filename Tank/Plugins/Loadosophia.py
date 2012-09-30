'''
Module to have Loadosophia.org integration
'''
from Tank.Core import AbstractPlugin
from Tank.Plugins.Phantom import PhantomPlugin
from Tank.Plugins.ApacheBenchmark import ApacheBenchmarkPlugin
from Tank.Plugins.Monitoring import MonitoringPlugin
import logging

class LoadosophiaPlugin(AbstractPlugin):
    '''
    Tank plugin with Loadosophia.org uploading 
    '''

    def __init__(self, core):
        '''
        Constructor
        '''
        AbstractPlugin.__init__(self, core)
        self.loadosophia = LoadosophiaClient()
        self.project_key = None
    
    def configure(self):
        self.loadosophia.set_token(self.get_option("token", ""))
        self.project_key = self.get_option("project", '')
    
    def post_process(self, retcode):
        main_file = None
        # phantom
        try:
            phantom = self.core.get_plugin_of_type(PhantomPlugin)
            main_file = phantom.phout_file
        except KeyError:
            self.log.debug("Phantom not found")
            
        # ab
        try:
            ab = self.core.get_plugin_of_type(ApacheBenchmarkPlugin)
            main_file = ab.out_file
        except KeyError:
            self.log.debug("AB not found")
        
        # monitoring
        mon_file = None
        try:
            mon = self.core.get_plugin_of_type(MonitoringPlugin)
            mon_file = mon.data_file
        except KeyError:
            self.log.debug("Phantom not found")
            
        self.loadosophia.send_results(self.project_key, main_file, [mon_file])
        return retcode

class LoadosophiaClient:
    def __init__(self):
        self.log = logging.getLogger(__name__)
    
    def send_results(self, project, result_files, monitoring_files):
        pass
    
    

