""" The central part of the tool: Core """
import datetime
import fnmatch
import importlib as il
import json
import logging
import os
import shutil
import socket
import tempfile
import time
import traceback
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

import pkg_resources
import sys
import platform

import yaml
from builtins import str

from yandextank.common.exceptions import PluginNotPrepared
from yandextank.common.interfaces import GeneratorPlugin
from yandextank.validator.validator import TankConfig

from ..common.util import update_status, execute, pid_exists

from ..common.resource import manager as resource
from ..plugins.Aggregator import Plugin as AggregatorPlugin
from ..plugins.Telegraf import Plugin as TelegrafPlugin

if sys.version_info[0] < 3:
    import ConfigParser
else:
    import configparser as ConfigParser

logger = logging.getLogger(__name__)


LOCK_FILE_WILDCARD = 'lunapark_*.lock'


class Job(object):
    def __init__(
            self,
            monitoring_plugin,
            aggregator_plugin,
            tank,
            generator_plugin=None):
        self.monitoring_plugin = monitoring_plugin
        self.aggregator_plugin = aggregator_plugin
        self.tank = tank
        self._phantom_info = None
        self.generator_plugin = generator_plugin

    def subscribe_plugin(self, plugin):
        self.aggregator_plugin.add_result_listener(plugin)
        try:
            self.monitoring_plugin.monitoring.add_listener(plugin)
        except AttributeError:
            logging.warning('Monitoring plugin is not enabled')

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
    """
    JMeter + dstat inspired :)
    """
    SECTION = 'core'
    SECTION_META = 'meta'
    PLUGIN_PREFIX = 'plugin_'
    PID_OPTION = 'pid'
    UUID_OPTION = 'uuid'

    def __init__(self, configs, artifacts_base_dir=None, artifacts_dir_name=None, cfg_depr=None):
        """

        :param configs: list of dict
        """
        self.raw_configs = configs
        self.config = TankConfig(self.raw_configs,
                                 with_dynamic_options=True,
                                 core_section=self.SECTION)
        self.status = {}
        self._plugins = None
        self._artifacts_dir = None
        self.artifact_files = {}
        self._artifacts_base_dir = None
        self.manual_start = False
        self.scheduled_start = None
        self.interrupted = False
        self.lock_file = None
        self.lock_dir = None
        self.taskset_path = None
        self.taskset_affinity = None
        self._job = None
        self.cfg_depr = cfg_depr
        self._cfg_snapshot = None

        self.interrupted = False
    #
    # def get_uuid(self):
    #     return self.uuid

    @property
    def cfg_snapshot(self):
        if not self._cfg_snapshot:
            if self.cfg_depr:
                output = StringIO()
                self.cfg_depr.write(output)
                self._cfg_snapshot = output.getvalue()
            else:
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

    def save_config(self, filename):
        self.config.save(filename)

    @property
    def artifacts_base_dir(self):
        if not self._artifacts_base_dir:
            artifacts_base_dir = os.path.expanduser(
                self.get_option(self.SECTION, "artifacts_base_dir"))
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

        self.taskset_path = self.get_option(
            self.SECTION, 'taskset_path')
        self.taskset_affinity = self.get_option(self.SECTION, 'affinity')

        for (plugin_name, plugin_path, plugin_cfg, cfg_updater) in self.config.plugins:
            logger.debug("Loading plugin %s from %s", plugin_name, plugin_path)
            if plugin_path is "yandextank.plugins.Overload":
                logger.warning(
                    "Deprecated plugin name: 'yandextank.plugins.Overload'\n"
                    "There is a new generic plugin now.\n"
                    "Correcting to 'yandextank.plugins.DataUploader overload'")
                plugin_path = "yandextank.plugins.DataUploader overload"
            try:
                plugin = il.import_module(plugin_path)
            except ImportError:
                if plugin_path.startswith("yatank_internal_"):
                    logger.warning(
                        "Deprecated plugin path format: %s\n"
                        "Tank plugins are now orginized using"
                        " namespace packages. Example:\n"
                        "    plugin_jmeter=yandextank.plugins.JMeter",
                        plugin_path)
                    plugin_path = plugin_path.replace(
                        "yatank_internal_", "yandextank.plugins.")
                if plugin_path.startswith("yatank_"):
                    logger.warning(
                        "Deprecated plugin path format: %s\n"
                        "Tank plugins are now orginized using"
                        " namespace packages. Example:\n"
                        "    plugin_jmeter=yandextank.plugins.JMeter",
                        plugin_path)

                    plugin_path = plugin_path.replace(
                        "yatank_", "yandextank.plugins.")
                logger.warning("Patched plugin path: %s", plugin_path)
                plugin = il.import_module(plugin_path)
            try:
                instance = getattr(plugin, 'Plugin')(self, cfg=plugin_cfg, cfg_updater=cfg_updater)
            except AttributeError:
                logger.warning(
                    "Deprecated plugin classname: %s. Should be 'Plugin'",
                    plugin)
                instance = getattr(
                    plugin, plugin_path.split('.')[-1] + 'Plugin')(self)

            self.register_plugin(self.PLUGIN_PREFIX + plugin_name, instance)

        logger.debug("Plugin instances: %s", self._plugins)

    @property
    def job(self):
        if not self._job:
            # monitoring plugin
            try:
                mon = self.get_plugin_of_type(TelegrafPlugin)
            except KeyError:
                logger.debug("Telegraf plugin not found:", exc_info=True)
                mon = None
            # aggregator plugin
            try:
                aggregator = self.get_plugin_of_type(AggregatorPlugin)
            except KeyError:
                logger.warning("Aggregator plugin not found:", exc_info=True)
                aggregator = None
            # generator plugin
            try:
                gen = self.get_plugin_of_type(GeneratorPlugin)
            except KeyError:
                logger.warning("Load generator not found:", exc_info=True)
                gen = None
            self._job = Job(monitoring_plugin=mon,
                            aggregator_plugin=aggregator,
                            generator_plugin=gen,
                            tank=socket.getfqdn())
        return self._job

    def plugins_configure(self):
        """        Call configure() on all plugins        """
        self.publish("core", "stage", "configure")

        logger.info("Configuring plugins...")
        if self.taskset_affinity != '':
            self.taskset(os.getpid(), self.taskset_path, self.taskset_affinity)

        for plugin in self.plugins.values():
            logger.debug("Configuring %s", plugin)
            plugin.configure()

    def plugins_prepare_test(self):
        """ Call prepare_test() on all plugins        """
        logger.info("Preparing test...")
        self.publish("core", "stage", "prepare")
        for plugin in self.plugins.values():
            logger.debug("Preparing %s", plugin)
            plugin.prepare_test()

    def plugins_start_test(self):
        """        Call start_test() on all plugins        """
        logger.info("Starting test...")
        self.publish("core", "stage", "start")
        for plugin in self.plugins.values():
            logger.debug("Starting %s", plugin)
            start_time = time.time()
            plugin.start_test()
            logger.info("Plugin {0:s} required {1:f} seconds to start".format(plugin,
                                                                              time.time() - start_time))

    def wait_for_finish(self):
        """
        Call is_test_finished() on all plugins 'till one of them initiates exit
        """

        logger.info("Waiting for test to finish...")
        logger.info('Artifacts dir: {}'.format(self.artifacts_dir))
        self.publish("core", "stage", "shoot")
        if not self.plugins:
            raise RuntimeError("It's strange: we have no plugins loaded...")

        while not self.interrupted:
            begin_time = time.time()
            for plugin in self.plugins.values():
                logger.debug("Polling %s", plugin)
                retcode = plugin.is_test_finished()
                if retcode >= 0:
                    return retcode
            end_time = time.time()
            diff = end_time - begin_time
            logger.debug("Polling took %s", diff)
            logger.debug("Tank status:\n%s", json.dumps(self.status, indent=2))
            # screen refresh every 0.5 s
            if diff < 0.5:
                time.sleep(0.5 - diff)
        return 1

    def plugins_end_test(self, retcode):
        """        Call end_test() on all plugins        """
        logger.info("Finishing test...")
        self.publish("core", "stage", "end")

        for plugin in self.plugins.values():
            logger.debug("Finalize %s", plugin)
            try:
                logger.debug("RC before: %s", retcode)
                plugin.end_test(retcode)
                logger.debug("RC after: %s", retcode)
            except Exception as ex:
                logger.error("Failed finishing plugin %s: %s", plugin, ex)
                logger.debug(
                    "Failed finishing plugin: %s", traceback.format_exc(ex))
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
            except Exception as ex:
                logger.error("Failed post-processing plugin %s: %s", plugin, ex)
                logger.debug(
                    "Failed post-processing plugin: %s",
                    traceback.format_exc(ex))
                if not retcode:
                    retcode = 1
        self.__collect_artifacts()

        return retcode

    def taskset(self, pid, path, affinity):
        if affinity:
            args = "%s -pc %s %s" % (path, affinity, pid)
            retcode, stdout, stderr = execute(
                args, shell=True, poll_period=0.1, catch_out=True)
            logger.debug('taskset stdout: %s', stdout)
            if retcode != 0:
                raise KeyError(stderr)
            else:
                logger.info(
                    "Enabled taskset for pid %s with affinity %s",
                    str(pid), affinity)

    def __collect_artifacts(self):
        logger.debug("Collecting artifacts")
        logger.info("Artifacts dir: %s", self.artifacts_dir)
        for filename, keep in self.artifact_files.items():
            try:
                self.__collect_file(filename, keep)
            except Exception as ex:
                logger.warn("Failed to collect file %s: %s", filename, ex)

    def get_option(self, section, option, default=None):
        return self.config.get_option(section, option)

    def set_option(self, section, option, value):
        """
        Set an option in storage
        """
        raise NotImplementedError

    def set_exitcode(self, code):
        self.config.validated['core']['exitcode'] = code

    def get_plugin_of_type(self, plugin_class):
        """
        Retrieve a plugin of desired class, KeyError raised otherwise
        """
        logger.debug("Searching for plugin: %s", plugin_class)
        matches = [plugin for plugin in self.plugins.values() if isinstance(plugin, plugin_class)]
        if len(matches) > 0:
            if len(matches) > 1:
                logger.debug(
                    "More then one plugin of type %s found. Using first one.",
                    plugin_class)
            return matches[-1]
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
            logger.warning("File not found to collect: %s", filename)
            return

        if os.path.exists(dest):
            # FIXME: 3 find a way to store artifacts anyway
            logger.warning("File already exists: %s", dest)
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

    # todo: remove lock_dir from config
    def get_lock_dir(self):
        if not self.lock_dir:
            self.lock_dir = self.get_option(
                self.SECTION, "lock_dir")
        return os.path.expanduser(self.lock_dir)

    def get_lock(self, force=False, lock_dir=None):
        lock_dir = lock_dir if lock_dir else self.get_lock_dir()
        if not force and self.is_locked(lock_dir):
            raise LockError("Lock file(s) found")

        fh, self.lock_file = tempfile.mkstemp(
            '.lock', 'lunapark_', lock_dir)
        os.close(fh)
        os.chmod(self.lock_file, 0o644)
        self.config.save(self.lock_file)

    def write_cfg_to_lock(self):
        if self.lock_file:
            self.config.save(self.lock_file)

    def release_lock(self):
        if self.lock_file and os.path.exists(self.lock_file):
            logger.debug("Releasing lock: %s", self.lock_file)
            os.remove(self.lock_file)

    @classmethod
    def is_locked(cls, lock_dir='/var/lock'):
        retcode = False
        for filename in os.listdir(lock_dir):
            if fnmatch.fnmatch(filename, LOCK_FILE_WILDCARD):
                full_name = os.path.join(lock_dir, filename)
                logger.info("Lock file is found: %s", full_name)
                try:
                    with open(full_name) as f:
                        running_cfg = yaml.load(f)
                    pid = running_cfg.get(TankCore.SECTION).get(cls.PID_OPTION)
                    if not pid:
                        logger.warning('Failed to get {}.{} from lock file {}'.format(TankCore.SECTION))
                    else:
                        if not pid_exists(int(pid)):
                            logger.debug(
                                "Lock PID %s not exists, ignoring and "
                                "trying to remove", pid)
                            try:
                                os.remove(full_name)
                            except Exception as exc:
                                logger.debug(
                                    "Failed to delete lock %s: %s", full_name, exc)
                        else:
                            retcode = True
                except Exception as exc:
                    logger.warn(
                        "Failed to load info from lock %s: %s", full_name, exc)
                    retcode = True
        return retcode

    def mkstemp(self, suffix, prefix, directory=None):
        """
        Generate temp file name in artifacts base dir
        and close temp file handle
        """
        if not directory:
            directory = self.artifacts_base_dir
        fd, fname = tempfile.mkstemp(suffix, prefix, directory)
        os.close(fd)
        os.chmod(fname, 0o644)  # FIXME: chmod to parent dir's mode?
        return fname

    def publish(self, publisher, key, value):
        update_status(self.status, [publisher] + key.split('.'), value)

    def close(self):
        """
        Call close() for all plugins
        """
        logger.info("Close allocated resources...")
        self.release_lock()
        for plugin in self.plugins.values():
            logger.debug("Close %s", plugin)
            try:
                plugin.close()
            except Exception as ex:
                logger.error("Failed closing plugin %s: %s", plugin, ex)
                logger.debug(
                    "Failed closing plugin: %s", traceback.format_exc(ex))

    @property
    def artifacts_dir(self):
        if not self._artifacts_dir:
            dir_name = self.get_option(self.SECTION, 'artifacts_dir')
            if not dir_name:
                date_str = datetime.datetime.now().strftime(
                    "%Y-%m-%d_%H-%M-%S.")
                dir_name = tempfile.mkdtemp("", date_str, self.artifacts_base_dir)
            elif not os.path.isdir(dir_name):
                os.makedirs(dir_name)
            os.chmod(dir_name, 0o755)
            self._artifacts_dir = os.path.abspath(dir_name)
        return self._artifacts_dir

    @staticmethod
    def get_user_agent():
        tank_agent = 'YandexTank/{}'.format(
            pkg_resources.require('yandextank')[0].version)
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


class ConfigManager(object):
    """ Option storage class """

    def __init__(self):
        self.file = None
        self.config = ConfigParser.ConfigParser()

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
        except ConfigParser.NoSectionError as ex:
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
