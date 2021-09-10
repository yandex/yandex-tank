""" The central part of the tool: Core """
import datetime
import fnmatch
import glob
import importlib as il
import json
import logging
import os
import shutil
import socket
import tempfile
import time
import traceback
import copy
import sys
import platform

import yaml
from builtins import str

from yandextank.common.const import RetCode
from yandextank.common.exceptions import PluginNotPrepared
from yandextank.common.interfaces import GeneratorPlugin, MonitoringPlugin, MonitoringDataListener
from yandextank.plugins.DataUploader.client import LPRequisites
from yandextank.validator.validator import TankConfig, ValidationError
from yandextank.aggregator import TankAggregator
from yandextank.common.util import pid_exists

from netort.resource import manager as resource
from netort.process import execute
from yandextank.version import VERSION

import configparser

logger = logging.getLogger(__name__)

CONFIGINITIAL = 'configinitial.yaml'
VALIDATED_CONF = 'validated_conf.yaml'


class Job(object):
    def __init__(
            self,
            monitoring_plugins,
            aggregator,
            tank,
            generator_plugin=None):
        """

        :type aggregator: TankAggregator
        :type monitoring_plugins: list of
        """
        self.monitoring_plugins = monitoring_plugins
        self.aggregator = aggregator
        self.tank = tank
        self._phantom_info = None
        self.generator_plugin = generator_plugin

    def subscribe_plugin(self, plugin):
        self.aggregator.add_result_listener(plugin)
        for monitoring_plugin in self.monitoring_plugins:
            monitoring_plugin.add_listener(plugin)

    @property
    def phantom_info(self):
        if self._phantom_info is None:
            raise PluginNotPrepared
        return self._phantom_info

    @phantom_info.setter
    def phantom_info(self, info):
        self._phantom_info = info


def parse_plugin(s):
    try:
        plugin, config_section = s.split()
    except ValueError:
        plugin, config_section = s, None
    return plugin, config_section


class LockError(Exception):
    pass


class TankCore(object):
    SECTION = 'core'
    SECTION_META = 'meta'
    PLUGIN_PREFIX = 'plugin_'
    PID_OPTION = 'pid'
    UUID_OPTION = 'uuid'
    API_JOBNO = 'api_jobno'

    def __init__(self, configs, interrupted_event, info):
        """

        :param configs: list of dict
        :param interrupted_event: threading.Event
        :type info: yandextank.common.interfaces.TankInfo
        """
        self.output = {}
        self.raw_configs = configs
        self.info = info
        self._plugins = None
        self._artifacts_dir = None
        self.artifact_files = {}
        self.artifacts_to_send = []
        self._artifacts_base_dir = None
        self.manual_start = False
        self.scheduled_start = None
        self.taskset_path = None
        self.taskset_affinity = None
        self._job = None
        self._cfg_snapshot = None

        self.interrupted = interrupted_event

        self.error_log = None
        self.monitoring_data_listeners = []

        error_output = 'validation_error.yaml'
        self.config, self.errors, self.configinitial = TankConfig(self.raw_configs,
                                                                  with_dynamic_options=True,
                                                                  core_section=self.SECTION,
                                                                  error_output=error_output).validate()
        if not self.config:
            raise ValidationError(self.errors)
        self.test_id = self.get_option(self.SECTION, 'artifacts_dir',
                                       datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S.%f"))
        self.lock_dir = self.get_option(self.SECTION, 'lock_dir')
        with open(os.path.join(self.artifacts_dir, CONFIGINITIAL), 'w') as f:
            yaml.dump(self.configinitial, f)
        self.add_artifact_file(error_output)
        self.add_artifact_to_send(LPRequisites.CONFIGINITIAL, yaml.dump(self.configinitial))
        configinfo = self.config.validated.copy()
        configinfo.setdefault(self.SECTION, {})
        configinfo[self.SECTION][self.API_JOBNO] = self.test_id
        self.add_artifact_to_send(LPRequisites.CONFIGINFO, yaml.dump(configinfo))
        with open(os.path.join(self.artifacts_dir, VALIDATED_CONF), 'w') as f:
            yaml.dump(configinfo, f)
        logger.info('New test id %s' % self.test_id)

    @property
    def cfg_snapshot(self):
        if not self._cfg_snapshot:
            self._cfg_snapshot = str(self.config)
        return self._cfg_snapshot

    @staticmethod
    def get_available_options():
        # todo: should take this from schema
        return [
            "artifacts_base_dir", "artifacts_dir",
            "taskset_path", "affinity"
        ]

    @property
    def plugins(self):
        """
        :returns: {plugin_name: plugin_class, ...}
        :rtype: dict
        """
        if self._plugins is None:
            self.load_plugins()
            if self._plugins is None:
                self._plugins = {}
        return self._plugins

    @property
    def artifacts_base_dir(self):
        if not self._artifacts_base_dir:
            try:
                artifacts_base_dir = os.path.abspath(self.get_option(self.SECTION, "artifacts_base_dir"))
            except ValidationError:
                artifacts_base_dir = os.path.abspath('logs')
            if not os.path.exists(artifacts_base_dir):
                os.makedirs(artifacts_base_dir)
                os.chmod(self.artifacts_base_dir, 0o755)
            self._artifacts_base_dir = artifacts_base_dir
        return self._artifacts_base_dir

    def load_plugins(self):
        """
        Tells core to take plugin options and instantiate plugin classes
        """
        logger.info("Loading plugins...")
        for (plugin_name, plugin_path, plugin_cfg) in self.config.plugins:
            logger.debug("Loading plugin %s from %s", plugin_name, plugin_path)
            if plugin_path == "yandextank.plugins.Overload":
                logger.warning(
                    "Deprecated plugin name: 'yandextank.plugins.Overload'\n"
                    "There is a new generic plugin now.\n"
                    "Correcting to 'yandextank.plugins.DataUploader overload'")
                plugin_path = "yandextank.plugins.DataUploader overload"
            try:
                logger.info("Trying to import module: {}".format(plugin_name))
                logger.info("Path: {}".format(plugin_path))
                plugin = il.import_module(plugin_path)
            except ImportError:
                logger.warning('Plugin name %s path %s import error', plugin_name, plugin_path)
                logger.debug('Plugin name %s path %s import error', plugin_name, plugin_path, exc_info=True)
                raise
            try:
                instance = getattr(plugin, 'Plugin')(self, cfg=plugin_cfg, name=plugin_name)
            except AttributeError:
                logger.warning('Plugin %s classname should be `Plugin`', plugin_name)
                raise
            else:
                self.register_plugin(self.PLUGIN_PREFIX + plugin_name, instance)
        logger.debug("Plugin instances: %s", self._plugins)

    @property
    def job(self):
        if not self._job:
            # monitoring plugin
            monitorings = [plugin for plugin in self.plugins.values() if isinstance(plugin, MonitoringPlugin)]
            # generator plugin
            try:
                gen = self.get_plugin_of_type(GeneratorPlugin)
            except KeyError:
                logger.warning("Load generator not found")
                gen = GeneratorPlugin(self, {}, 'generator dummy')
            # aggregator
            aggregator = TankAggregator(gen)
            self._job = Job(monitoring_plugins=monitorings,
                            generator_plugin=gen,
                            aggregator=aggregator,
                            tank=socket.getfqdn())
        return self._job

    def plugins_configure(self):
        """        Call configure() on all plugins        """
        self.publish("core", "stage", "configure")

        logger.info("Configuring plugins...")
        self.taskset_affinity = self.get_option(self.SECTION, 'affinity')
        if self.taskset_affinity:
            self.__setup_taskset(self.taskset_affinity, pid=os.getpid())

        for plugin in self.plugins.values():
            if not self.interrupted.is_set():
                logger.debug("Configuring %s", plugin)
                plugin.configure()
                if isinstance(plugin, MonitoringDataListener):
                    self.monitoring_data_listeners.append(plugin)

    def plugins_prepare_test(self):
        """ Call prepare_test() on all plugins        """
        logger.info("Preparing test...")
        self.publish("core", "stage", "prepare")
        for plugin in self.plugins.values():
            if not self.interrupted.is_set():
                logger.debug("Preparing %s", plugin)
                plugin.prepare_test()

    def plugins_start_test(self):
        """        Call start_test() on all plugins        """
        if not self.interrupted.is_set():
            logger.info("Starting test...")
            self.publish("core", "stage", "start")
            self.job.aggregator.start_test()
            for plugin_name, plugin in self.plugins.items():
                logger.debug("Starting %s", plugin)
                start_time = time.time()
                plugin.start_test()
                logger.info("Plugin {0:s} required {1:f} seconds to start".format(plugin_name,
                                                                                  time.time() - start_time))
            self.publish('generator', 'test_start', self.job.generator_plugin.start_time)

    def wait_for_finish(self):
        """
        Call is_test_finished() on all plugins 'till one of them initiates exit
        """
        if not self.interrupted.is_set():
            logger.info("Waiting for test to finish...")
            logger.info('Artifacts dir: {dir}'.format(dir=self.artifacts_dir))
            self.publish("core", "stage", "shoot")
            if not self.plugins:
                raise RuntimeError("It's strange: we have no plugins loaded...")

        while not self.interrupted.is_set():
            begin_time = time.time()
            aggr_retcode = self.job.aggregator.is_test_finished()
            if aggr_retcode >= 0:
                return aggr_retcode
            for plugin_name, plugin in self.plugins.items():
                logger.debug("Polling %s", plugin)
                try:
                    retcode = plugin.is_test_finished()
                    if retcode >= 0:
                        return retcode
                except Exception:
                    logger.warning('Plugin {} failed:'.format(plugin_name), exc_info=True)
                    if isinstance(plugin, GeneratorPlugin):
                        return RetCode.ERROR
                    else:
                        logger.warning('Disabling plugin {}'.format(plugin_name))
                        plugin.is_test_finished = lambda: RetCode.CONTINUE
            end_time = time.time()
            diff = end_time - begin_time
            logger.debug("Polling took %s", diff)
            logger.debug("Tank status: %s", json.dumps(self.info.get_info_dict()))
            # screen refresh every 0.5 s
            if diff < 0.5:
                time.sleep(0.5 - diff)
        return 1

    def plugins_end_test(self, retcode):
        """        Call end_test() on all plugins        """
        logger.info("Finishing test...")
        self.publish("core", "stage", "end")
        self.publish('generator', 'test_end', time.time())
        logger.info("Stopping load generator and aggregator")
        retcode = self.job.aggregator.end_test(retcode)
        logger.debug("RC after: %s", retcode)

        logger.info('Stopping monitoring')
        for plugin in self.job.monitoring_plugins:
            logger.info('Stopping %s', plugin)
            retcode = plugin.end_test(retcode) or retcode
            logger.info('RC after: %s', retcode)

        for plugin in [p for p in self.plugins.values() if
                       p is not self.job.generator_plugin and p not in self.job.monitoring_plugins]:
            logger.debug("Finalize %s", plugin)
            try:
                logger.debug("RC before: %s", retcode)
                retcode = plugin.end_test(retcode)
                logger.debug("RC after: %s", retcode)
            except Exception:  # FIXME too broad exception clause
                logger.error("Failed finishing plugin %s", plugin, exc_info=True)
                if not retcode:
                    retcode = 1
        return retcode

    def plugins_post_process(self, retcode):
        """
        Call post_process() on all plugins
        """
        logger.info("Post-processing test...")
        self.publish("core", "stage", "post_process")
        for plugin in self.plugins.values():
            logger.debug("Post-process %s", plugin)
            try:
                logger.debug("RC before: %s", retcode)
                retcode = plugin.post_process(retcode)
                logger.debug("RC after: %s", retcode)
            except Exception:  # FIXME too broad exception clause
                logger.error("Failed post-processing plugin %s", plugin, exc_info=True)
                if not retcode:
                    retcode = 1
        return retcode

    def publish_monitoring_data(self, data):
        """sends pending data set to listeners"""
        for plugin in self.monitoring_data_listeners:
            # deep copy to ensure each listener gets it's own copy
            try:
                plugin.monitoring_data(copy.deepcopy(data))
            except Exception:
                logger.error("Plugin failed to process monitoring data", exc_info=True)

    def __setup_taskset(self, affinity, pid=None, args=None):
        """ if pid specified: set process w/ pid `pid` CPU affinity to specified `affinity` core(s)
            if args specified: modify list of args for Popen to start w/ taskset w/ affinity `affinity`
        """
        self.taskset_path = self.get_option(self.SECTION, 'taskset_path')

        if args:
            return [self.taskset_path, '-c', affinity] + args

        if pid:
            args = "%s -pc %s %s" % (self.taskset_path, affinity, pid)
            retcode, stdout, stderr = execute(args, shell=True, poll_period=0.1, catch_out=True)
            logger.debug('taskset for pid %s stdout: %s', pid, stdout)
            if retcode == 0:
                logger.info("Enabled taskset for pid %s with affinity %s", str(pid), affinity)
            else:
                logger.debug('Taskset setup failed w/ retcode :%s', retcode)
                raise KeyError(stderr)

    def _collect_artifacts(self, validation_failed=False):
        logger.debug("Collecting artifacts")
        logger.info("Artifacts dir: %s", self.artifacts_dir)
        for filename, keep in self.artifact_files.items():
            try:
                self.__collect_file(filename, keep)
            except Exception as ex:
                logger.warn("Failed to collect file %s: %s", filename, ex)

    def get_option(self, section, option, default=None):
        return self.config.get_option(section, option, default)

    def set_option(self, section, option, value):
        """
        Set an option in storage
        """
        raise NotImplementedError

    def set_exitcode(self, code):
        self.output['core']['exitcode'] = code

    def get_plugin_of_type(self, plugin_class):
        """
        Retrieve a plugin of desired class, KeyError raised otherwise
        """
        logger.debug("Searching for plugin: %s", plugin_class)
        matches = [plugin for plugin in self.plugins.values() if isinstance(plugin, plugin_class)]
        if matches:
            if len(matches) > 1:
                logger.debug(
                    "More then one plugin of type %s found. Using first one.",
                    plugin_class)
            return matches[-1]
        else:
            raise KeyError("Requested plugin type not found: %s" % plugin_class)

    def get_plugins_of_type(self, plugin_class):
        """
        Retrieve a list of plugins of desired class, KeyError raised otherwise
        """
        logger.debug("Searching for plugins: %s", plugin_class)
        matches = [plugin for plugin in self.plugins.values() if isinstance(plugin, plugin_class)]
        if matches:
            return matches
        else:
            raise KeyError("Requested plugin type not found: %s" % plugin_class)

    def get_jobno(self, plugin_name='plugin_lunapark'):
        uploader_plugin = self.plugins[plugin_name]
        return uploader_plugin.lp_job.number

    def __collect_file(self, filename, keep_original=False):
        """
        Move or copy single file to artifacts dir
        """
        dest = self.artifacts_dir + '/' + os.path.basename(filename)
        logger.debug("Collecting file: %s to %s", filename, dest)
        if not filename or not os.path.exists(filename):
            logger.info("File not found to collect: %s", filename)
            return

        if os.path.exists(dest):
            # FIXME: 3 find a way to store artifacts anyway
            logger.info("File already exists: %s", dest)
            return

        if keep_original:
            shutil.copy(filename, self.artifacts_dir)
        else:
            shutil.move(filename, self.artifacts_dir)

        os.chmod(dest, 0o644)

    def add_artifact_file(self, filename, keep_original=False):
        """
        Add file to be stored as result artifact on post-process phase
        """
        if filename:
            logger.debug(
                "Adding artifact file to collect (keep=%s): %s", keep_original,
                filename)
            self.artifact_files[filename] = keep_original

    def add_artifact_to_send(self, lp_requisites, content):
        self.artifacts_to_send.append((lp_requisites, content))

    def apply_shorthand_options(self, options, default_section='DEFAULT'):
        for option_str in options:
            key, value = option_str.split('=')
            try:
                section, option = key.split('.')
            except ValueError:
                section = default_section
                option = key
            logger.debug(
                "Override option: %s => [%s] %s=%s", option_str, section,
                option, value)
            self.set_option(section, option, value)

    def mkstemp(self, suffix, prefix, directory=None):
        """
        Generate temp file name in artifacts base dir
        and close temp file handle
        """
        if not directory:
            directory = self.artifacts_dir
        fd, fname = tempfile.mkstemp(suffix, prefix, directory)
        os.close(fd)
        os.chmod(fname, 0o644)  # FIXME: chmod to parent dir's mode?
        return fname

    def publish(self, publisher, key, value):
        self.info.update([publisher] + key.split('.'), value)

    def close(self):
        """
        Call close() for all plugins
        """
        logger.info("Close allocated resources...")
        for plugin in self.plugins.values():
            logger.debug("Close %s", plugin)
            try:
                plugin.close()
            except Exception as ex:
                logger.error("Failed closing plugin %s: %s", plugin, ex)
                logger.debug(
                    "Failed closing plugin: %s", traceback.format_exc())

    @property
    def artifacts_dir(self):
        if not self._artifacts_dir:
            new_path = os.path.join(self.artifacts_base_dir, self.test_id)
            if not os.path.isdir(new_path):
                os.makedirs(new_path)
            os.chmod(new_path, 0o755)
            self._artifacts_dir = os.path.abspath(new_path)
        return self._artifacts_dir

    @staticmethod
    def get_user_agent():
        tank_agent = 'YandexTank/{}'.format(VERSION)
        py_info = sys.version_info
        python_agent = 'Python/{}.{}.{}'.format(
            py_info[0], py_info[1], py_info[2])
        os_agent = 'OS/{}'.format(platform.platform())
        return ' '.join((tank_agent, python_agent, os_agent))

    def register_plugin(self, plugin_name, instance):
        if self._plugins is None:
            self._plugins = {}
        if self._plugins.get(plugin_name, None) is not None:
            logger.exception('Plugins\' names should diverse')
        self._plugins[plugin_name] = instance

    def save_cfg(self, path):
        self.config.dump(path)

    def plugins_cleanup(self):
        for plugin_name, plugin in self.plugins.items():
            logger.info('Cleaning up plugin {}'.format(plugin_name))
            plugin.cleanup()


class Lock(object):
    PID = 'pid'
    TEST_ID = 'test_id'
    TEST_DIR = 'test_dir'
    LOCK_FILE_WILDCARD = 'lunapark_*.lock'

    def __init__(self, test_id, test_dir, pid=None):
        self.test_id = test_id
        self.test_dir = test_dir
        self.pid = pid if pid is not None else os.getpid()
        self.info = {
            self.PID: self.pid,
            self.TEST_ID: self.test_id,
            self.TEST_DIR: self.test_dir
        }
        self.lock_file = None

    def acquire(self, lock_dir, ignore=False):
        is_locked = self.is_locked(lock_dir)
        if not ignore and is_locked:
            raise LockError("Lock file(s) found\n{}".format(is_locked))
        prefix, suffix = self.LOCK_FILE_WILDCARD.split('*')
        fh, self.lock_file = tempfile.mkstemp(suffix, prefix, lock_dir)
        os.close(fh)
        with open(self.lock_file, 'w') as f:
            yaml.dump(self.info, f)
        os.chmod(self.lock_file, 0o644)
        return self

    def release(self):
        if self.lock_file is not None and os.path.exists(self.lock_file):
            logger.info("Releasing lock: %s", self.lock_file)
            os.remove(self.lock_file)
        else:
            logger.warning('Lock file not found')

    @classmethod
    def load(cls, path):
        with open(path) as f:
            info = yaml.load(f, Loader=yaml.FullLoader)
        pid = info.get(cls.PID)
        test_id = info.get(cls.TEST_ID)
        test_dir = info.get(cls.TEST_DIR)
        lock = Lock(test_id, test_dir, pid)
        lock.lock_file = path
        return lock

    def __str__(self):
        return str(self.info)

    @classmethod
    def is_locked(cls, lock_dir='/var/lock'):
        for filename in os.listdir(lock_dir):
            if fnmatch.fnmatch(filename, cls.LOCK_FILE_WILDCARD):
                full_name = os.path.join(lock_dir, filename)
                logger.info("Lock file is found: %s", full_name)
                try:
                    running_lock = cls.load(full_name)
                    if not running_lock.pid:
                        msg = 'Failed to get {} from lock file {}.'.format(cls.PID,
                                                                           full_name)
                        logger.warning(msg)
                        return msg
                    else:
                        if not pid_exists(int(running_lock.pid)):
                            logger.info("Lock PID %s not exists, ignoring and trying to remove", running_lock.pid)
                            try:
                                os.remove(full_name)
                            except Exception as exc:
                                logger.warning("Failed to delete lock %s: %s", full_name, exc)
                            return False
                        else:
                            return "Another test is running: {}".format(running_lock)
                except Exception:
                    msg = "Failed to load info from lock %s" % full_name
                    logger.warn(msg, exc_info=True)
                    return msg
        return False

    @classmethod
    def running_ids(cls, lock_dir='/var/lock'):
        return [Lock.load(fname).test_id for fname in glob.glob(os.path.join(lock_dir, cls.LOCK_FILE_WILDCARD))]


class ConfigManager(object):
    """ Option storage class """

    def __init__(self):
        self.file = None
        self.config = configparser.RawConfigParser(strict=False)

    def load_files(self, configs):
        """         Read configs set into storage        """
        logger.debug("Reading configs: %s", configs)
        config_filenames = [resource.resource_filename(config) for config in configs]
        try:
            self.config.read(config_filenames)
        except Exception as ex:
            logger.error("Can't load configs: %s", ex)
            raise ex

    def flush(self, filename=None):
        """        Flush current stat to file        """
        if not filename:
            filename = self.file

        if filename:
            with open(filename, 'w') as handle:
                self.config.write(handle)

    def get_options(self, section, prefix=''):
        """ Get options list with requested prefix """
        res = []
        try:
            for option in self.config.options(section):
                if not prefix or option.find(prefix) == 0:
                    res += [(
                        option[len(prefix):], self.config.get(section, option))]
        except configparser.NoSectionError as ex:
            logger.warning("No section: %s", ex)

        logger.debug(
            "Section: [%s] prefix: '%s' options:\n%s", section, prefix, res)
        return res

    def find_sections(self, prefix):
        """ return sections with specified prefix """
        res = []
        for section in self.config.sections():
            if section.startswith(prefix):
                res.append(section)
        return res
