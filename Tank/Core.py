# TODO: distinct private from public in classes
from ConfigParser import NoSectionError
import ConfigParser
import logging
import os
import shutil
import sys
import tempfile
import time
import traceback

class TankCore:
    """
    JMeter+Dstat inspired :)
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
         
    def load_configs(self, configs):
        self.log.info("Loading configs...")
        self.config.load_files(configs)
        self.config.flush()
        self.add_artifact_file(self.config.file)

         
    def load_plugins(self):
        self.log.info("Loading plugins...")
        self.log.debug("sys.path: %s", sys.path)

        self.artifacts_base_dir = self.get_option(self.SECTION, "artifacts_base_dir", tempfile.gettempdir())

        for (plugin_name, plugin_path) in self.config.get_options(self.SECTION, self.PLUGIN_PREFIX):
            if not plugin_path:
                self.log.warning("Seems the plugin %s was disabled", plugin_name)
                continue
            instance = self.load_plugin(plugin_name, plugin_path)
            self.plugins[instance.get_key()] = instance 
            self.plugins_order.append(instance.get_key())
        self.log.debug("Plugin instances: %s", self.plugins)
        self.log.debug("Plugins order: %s", self.plugins_order)
            
    def load_plugin(self, name, path):
        self.log.debug("Loading plugin %s from %s", name, path)
        for basedir in sys.path:
            if os.path.exists(basedir + '/' + path):
                sys.path.append(os.path.dirname(basedir + '/' + path))
        res = None
        classname = os.path.basename(path)[:-3]
        exec ("import " + classname)
        script = "res=" + classname + "." + classname + "Plugin(self)"
        self.log.debug("Exec: " + script)
        exec (script)
        self.log.debug("Instantiated: %s", res);
        return res

    def plugins_check_config(self):
        self.log.info("Configuring plugins...")
        for plugin_key in self.plugins_order:
            plugin = self.get_plugin_by_key(plugin_key)
            self.log.debug("Configuring %s", plugin)
            plugin.configure()
            self.config.flush()
        
    def plugins_prepare_test(self):
        self.log.info("Preparing test...")
        for plugin_key in self.plugins_order:
            plugin = self.get_plugin_by_key(plugin_key)
            self.log.debug("Preparing %s", plugin)
            plugin.prepare_test()
        
    def plugins_start_test(self):
        self.log.info("Starting test...")
        for plugin_key in self.plugins_order:
            plugin = self.get_plugin_by_key(plugin_key)
            self.log.debug("Starting %s", plugin)
            plugin.start_test()
            
    def wait_for_finish(self):
        self.log.info("Waiting for test to finish...")
        if not self.plugins:
            raise RuntimeError("It's strange: we have no plugins loaded...")
        
        while True:
            begin_time = time.time()
            for plugin_key in self.plugins_order:
                plugin = self.get_plugin_by_key(plugin_key)
                self.log.debug("Polling %s", plugin)
                rc = plugin.is_test_finished()
                if rc >= 0:
                    return rc;
            end_time = time.time()
            diff = end_time - begin_time
            self.log.debug("Polling took %s", diff)
            if (diff < 1):
                time.sleep(1 - diff)
        raise RuntimeError("Unreachable line hit")
            

    def plugins_end_test(self, rc):
        self.log.info("Finishing test...")
        
        for plugin_key in self.plugins_order:
            plugin = self.get_plugin_by_key(plugin_key)
            self.log.debug("Finalize %s", plugin)
            try:
                plugin.end_test(rc)
            except Exception, ex:
                self.log.error("Failed finishing plugin %s: %s", plugin, ex)
                self.log.debug("Failed finishing plugin: %s", traceback.format_exc(ex));
                if not rc:
                    rc = 1

        return rc
    
    def plugins_post_process(self, rc):
        self.log.info("Post-processing test...")
        
        if not self.artifacts_dir: 
            self.artifacts_dir = tempfile.mkdtemp(".artifacts", "tank_", self.artifacts_base_dir)
        else:
            if not os.path.isdir(self.artifacts_dir):
                os.makedirs(self.artifacts_dir)
        self.log.info("Artifacts dir: %s", self.artifacts_dir)

        for plugin_key in self.plugins_order:
            plugin = self.get_plugin_by_key(plugin_key)
            self.log.debug("Post-process %s", plugin)
            try:
                plugin.post_process(rc)
            except Exception, ex:
                self.log.error("Failed post-processing plugin %s: %s", plugin, ex)
                self.log.debug("Failed post-processing plugin: %s", traceback.format_exc(ex));
                del self.plugins[plugin_key]
                if not rc:
                    rc = 1

        for (filename, keep) in self.artifact_files.items():
            self.collect_file(filename, keep)
        
        return rc
    
    def get_option(self, section, option, default=None):
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
        if not self.config.config.has_section(section):
            self.config.config.add_section(section)
        self.config.config.set(section, option, value)
        self.config.flush()
             
    def get_plugin_of_type(self, needle):
        self.log.debug("Searching for plugin: %s", needle)
        key = needle.get_key()
        
        return self.get_plugin_by_key(key)
        
    def get_plugin_by_key(self, key):
        if key in self.plugins.keys():
            return self.plugins[key]
        
        ext = os.path.splitext(key)[1].lower()
        
        if ext == '.py' and key + 'c' in self.plugins.keys(): # .py => .pyc
            return self.plugins[key + 'c']
        
        if ext == '.pyc' and key[:-1] in self.plugins.keys(): # .pyc => .py:
            return self.plugins[key[:-1]]
        
        raise KeyError("Requested plugin type not found: %s", key)  
    
    def collect_file(self, filename, keep_original=False):
        if not self.artifacts_dir:
            self.log.warning("No artifacts dir configured")
            return            
        
        self.log.debug("Collecting file: %s to %s", filename, self.artifacts_dir + '/' + os.path.basename(filename))
        if not filename or not os.path.exists(filename):
            self.log.warning("File not found to collect: %s", filename)
            return
        
        if keep_original:
            shutil.copy(filename, self.artifacts_dir)
        else:
            shutil.move(filename, self.artifacts_dir)

    
    def add_artifact_file(self, filename, keep_original=False):
        if filename:
            self.artifact_files[filename] = keep_original
    
            
class ConfigManager:
    def __init__(self):
        self.file = tempfile.mkstemp(".conf", "lp_")[1]
        self.log = logging.getLogger(__name__)
        self.config = ConfigParser.ConfigParser()
            
    def set_out_file(self, filename):
        self.file = filename
    
    def load_files(self, configs):
        self.log.debug("Reading configs: %s", configs)
        try:
            self.config.read(configs)
        except Exception as ex:
            self.log.error("Can't load configs: %s", ex)
            raise ex
                    
    def flush(self, filename=None):
        if not filename:
            filename = self.file
        self.log.debug("Flushing config to: %s", filename)
        with open(filename, 'wb') as configfile:
            self.config.write(configfile)
                    
    def get_options(self, section, prefix=''):
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
                
        self.log.debug("Found options: %s", res);
        return res

class AbstractPlugin:
    @staticmethod
    def get_key():
        raise TypeError("Abstract method needs to be overridden")
    def __init__(self, core):
        self.log = logging.getLogger(__name__)
        self.core = core
    def configure(self):
        raise TypeError("Abstract method needs to be overridden")
    def prepare_test(self):
        raise TypeError("Abstract method needs to be overridden")
    def start_test(self):
        raise TypeError("Abstract method needs to be overridden")
    def is_test_finished(self):
        return -1;
    def end_test(self, retcode):
        raise TypeError("Abstract method needs to be overridden")
    def post_process(self, rc):
        return rc;

    def get_option(self, option_name, default_value=None):
        return self.core.get_option(self.SECTION, option_name, default_value)