'''
The central part of the tool: Core
'''
from ConfigParser import NoSectionError
import ConfigParser
import logging
import os
import shutil
import sys
import tempfile
import time
import traceback
import datetime

# TODO: 3 add ability to set options in "section.option" style in DEFAULT section

class TankCore:
    """
    JMeter + dstat inspired :)
    """
    SECTION = 'tank'
    PLUGIN_PREFIX = 'plugin_'
    
    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.config = ConfigManager()
        self.plugins = {}
        self.artifacts_dir = None
        self.artifact_files = {}
        self.plugins_order = []
        self.artifacts_base_dir = '.'
         
    def load_configs(self, configs):
        '''
        Tells core to load configs set into options storage
        '''
        self.log.info("Loading configs...")
        self.config.load_files(configs)
        self.config.flush()
        self.add_artifact_file(self.config.file)

         
    def load_plugins(self):
        '''
        Tells core to take plugin options and instantiate plugin classes
        '''
        self.log.info("Loading plugins...")
        self.log.debug("sys.path: %s", sys.path)

        self.artifacts_base_dir = os.path.expanduser(self.get_option(self.SECTION, "artifacts_base_dir", self.artifacts_base_dir))
        self.artifacts_dir = self.get_option(self.SECTION, "artifacts_dir", "")
        if self.artifacts_dir:
            self.artifacts_dir = os.path.expanduser(self.artifacts_dir)

        for (plugin_name, plugin_path) in self.config.get_options(self.SECTION, self.PLUGIN_PREFIX):
            if not plugin_path:
                self.log.warning("Seems the plugin '%s' was disabled", plugin_name)
                continue
            instance = self.__load_plugin(plugin_name, plugin_path)
            self.plugins[instance.get_key()] = instance 
            self.plugins_order.append(instance.get_key())
        self.log.debug("Plugin instances: %s", self.plugins)
        self.log.debug("Plugins order: %s", self.plugins_order)
            
    def __load_plugin(self, name, path):
        '''
        Load single plugin using 'exec' statement
        '''
        self.log.debug("Loading plugin %s from %s", name, path)
        for basedir in [''] + sys.path:
            new_dir = basedir + '/' + path
            if os.path.exists(basedir + '/' + path):
                self.log.debug('Append to path basedir of: %s', new_dir)
                sys.path.append(os.path.dirname(new_dir))
        res = None
        classname = os.path.basename(path)[:-3]
        exec ("import " + classname)
        script = "res=" + classname + "." + classname + "Plugin(self)"
        self.log.debug("Exec: " + script)
        exec (script)
        self.log.debug("Instantiated: %s", res)
        return res

    def plugins_configure(self):
        '''
        Call configure() on all plugins
        '''
        if not os.path.exists(self.artifacts_base_dir): 
            os.makedirs(self.artifacts_base_dir)
        self.log.info("Configuring plugins...")
        for plugin_key in self.plugins_order:
            plugin = self.__get_plugin_by_key(plugin_key)
            self.log.debug("Configuring %s", plugin)
            plugin.configure()
            self.config.flush()
        
    def plugins_prepare_test(self):
        '''
        Call prepare_test() on all plugins
        '''
        self.log.info("Preparing test...")
        for plugin_key in self.plugins_order:
            plugin = self.__get_plugin_by_key(plugin_key)
            self.log.debug("Preparing %s", plugin)
            plugin.prepare_test()
        
    def plugins_start_test(self):
        '''
        Call start_test() on all plugins
        '''
        self.log.info("Starting test...")
        for plugin_key in self.plugins_order:
            plugin = self.__get_plugin_by_key(plugin_key)
            self.log.debug("Starting %s", plugin)
            plugin.start_test()
            
    def wait_for_finish(self):
        '''
        Call is_test_finished() on all plugins 'till one of them initiates exit
        '''

        self.log.info("Waiting for test to finish...")
        if not self.plugins:
            raise RuntimeError("It's strange: we have no plugins loaded...")
        
        while True:
            begin_time = time.time()
            for plugin_key in self.plugins_order:
                plugin = self.__get_plugin_by_key(plugin_key)
                self.log.debug("Polling %s", plugin)
                retcode = plugin.is_test_finished()
                if retcode >= 0:
                    return retcode
            end_time = time.time()
            diff = end_time - begin_time
            self.log.debug("Polling took %s", diff)
            if (diff < 1):
                time.sleep(1 - diff)
        raise RuntimeError("Unreachable line hit")
            

    def plugins_end_test(self, retcode):
        '''
        Call end_test() on all plugins
        '''
        self.log.info("Finishing test...")
        
        for plugin_key in self.plugins_order:
            plugin = self.__get_plugin_by_key(plugin_key)
            self.log.debug("Finalize %s", plugin)
            try:
                plugin.end_test(retcode)
            except Exception, ex:
                self.log.error("Failed finishing plugin %s: %s", plugin, ex)
                self.log.debug("Failed finishing plugin: %s", traceback.format_exc(ex))
                if not retcode:
                    retcode = 1

        return retcode
    
    def plugins_post_process(self, retcode):
        '''
        Call post_process() on all plugins
        '''
        self.log.info("Post-processing test...")
        
        if not self.artifacts_dir: 
            date_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S.")
            self.artifacts_dir = tempfile.mkdtemp("", date_str, self.artifacts_base_dir)
        else:
            if not os.path.isdir(self.artifacts_dir):
                os.makedirs(self.artifacts_dir)
        self.log.info("Artifacts dir: %s", self.artifacts_dir)

        for plugin_key in self.plugins_order:
            plugin = self.__get_plugin_by_key(plugin_key)
            self.log.debug("Post-process %s", plugin)
            try:
                plugin.post_process(retcode)
            except Exception, ex:
                self.log.error("Failed post-processing plugin %s: %s", plugin, ex)
                self.log.debug("Failed post-processing plugin: %s", traceback.format_exc(ex))
                del self.plugins[plugin_key]
                if not retcode:
                    retcode = 1

        for (filename, keep) in self.artifact_files.items():
            self.__collect_file(filename, keep)
        
        return retcode
    
    def get_option(self, section, option, default=None):
        '''
        Get an option from option storage
        '''
        if not self.config.config.has_section(section):
            self.log.debug("No section '%s', adding", section)
            self.config.config.add_section(section)
            
        try:
            self.log.debug("Getting option: %s.%s", section, option)
            return self.config.config.get(section, option)
        except ConfigParser.NoOptionError as ex:
            if default != None:
                self.config.config.set(section, option, default)
                self.config.flush()
                return default
            else:
                self.log.warn("Mandatory option %s was not found in section %s", option, section)
                raise ex

    def set_option(self, section, option, value):
        '''
        Set an option in storage
        '''
        if not self.config.config.has_section(section):
            self.config.config.add_section(section)
        self.config.config.set(section, option, value)
        self.config.flush()
             
    def get_plugin_of_type(self, needle):
        '''
        Retrieve a plugin of desired class, KeyError raised otherwise
        '''
        self.log.debug("Searching for plugin: %s", needle)
        key = needle.get_key()
        
        return self.__get_plugin_by_key(key)
        
    def __get_plugin_by_key(self, key):
        '''
        Get plugin from loaded by its key
        '''
        if key in self.plugins.keys():
            return self.plugins[key]
        
        ext = os.path.splitext(key)[1].lower()
        
        if ext == '.py' and key + 'c' in self.plugins.keys(): # .py => .pyc
            return self.plugins[key + 'c']
        
        if ext == '.pyc' and key[:-1] in self.plugins.keys(): # .pyc => .py:
            return self.plugins[key[:-1]]
        
        raise KeyError("Requested plugin type not found: %s" % key)  
    
    def __collect_file(self, filename, keep_original=False):
        '''
        Move or copy single file to artifacts dir
        '''
        if not self.artifacts_dir:
            self.log.warning("No artifacts dir configured")
            return            
        
        dest = self.artifacts_dir + '/' + os.path.basename(filename)
        self.log.debug("Collecting file: %s to %s", filename, dest)
        if not filename or not os.path.exists(filename):
            self.log.warning("File not found to collect: %s", filename)
            return
        
        if os.path.exists(dest):
            # FIXME: 2 find a way to store artifacts anyway
            self.log.warning("File already exists: %s", dest)
            return
                
        if keep_original:
            shutil.copy(filename, self.artifacts_dir)
        else:
            shutil.move(filename, self.artifacts_dir)

    
    def add_artifact_file(self, filename, keep_original=False):
        '''
        Add file to be stored as result artifact on post-process phase
        '''
        if filename:
            self.artifact_files[filename] = keep_original
    
            
class ConfigManager:
    '''
    Option storage class
    '''
    def __init__(self):
        self.file = tempfile.mkstemp(".conf", "lp_")[1]
        self.log = logging.getLogger(__name__)
        self.config = ConfigParser.ConfigParser()
            
    def set_out_file(self, filename):
        '''
        set path to file where current options set state will be saved
        '''
        self.file = filename
    
    def load_files(self, configs):
        '''
        Read configs set into storage
        '''
        self.log.debug("Reading configs: %s", configs)
        try:
            self.config.read(configs)
        except Exception as ex:
            self.log.error("Can't load configs: %s", ex)
            raise ex
                    
    def flush(self, filename=None):
        '''
        Flush current stat to file
        '''
        if not filename:
            filename = self.file
        self.log.debug("Flushing config to: %s", filename)
        with open(filename, 'wb') as configfile:
            self.config.write(configfile)
                    
    def get_options(self, section, prefix=''):
        '''
        Get options list with requested prefix
        '''
        res = []
        self.log.debug("Looking in section '%s' for options starting with '%s'", section, prefix)
        try :
            for option in self.config.options(section):
                self.log.debug("Option: %s", option)
                if not prefix or option.find(prefix) == 0:
                    self.log.debug("Option: %s matched", option)
                    res += [(option[len(prefix):], self.config.get(section, option))]
        except NoSectionError, ex:
            self.log.debug("No section: %s", ex)
                
        self.log.debug("Found options: %s", res)
        return res

class AbstractPlugin:
    '''
    Parent class for all plugins/modules
    '''

    SECTION = 'DEFAULT'
    
    @staticmethod
    def get_key():
        '''
        Get dictionary key for plugin, should point to __file__ magic constant
        '''
        raise TypeError("Abstract method needs to be overridden")
    
    def __init__(self, core):
        self.log = logging.getLogger(__name__)
        self.core = core
        
    def configure(self):
        '''
        A stage to read config values and instantiate objects
        '''
        pass
    
    def prepare_test(self):
        '''
        Test preparation tasks
        '''
        pass
    
    def start_test(self):
        '''
        Launch test process
        '''
        pass
    
    def is_test_finished(self):
        '''
        Polling call, if result differs from -1 then test end will be triggeted
        '''
        return -1
    
    def end_test(self, retcode):
        '''
        Stop processes launched at 'start_test', change return code if necessary
        '''
        return retcode
    
    def post_process(self, retcode):
        '''
        Post-process test data
        '''
        return retcode

    def get_option(self, option_name, default_value=None):
        '''
        Wrapper to get option from plugins' section
        '''
        return self.core.get_option(self.SECTION, option_name, default_value)

    def set_option(self, option_name, value):
        '''
        Wrapper to set option to plugins' section
        '''
        return self.core.set_option(self.SECTION, option_name, value)
