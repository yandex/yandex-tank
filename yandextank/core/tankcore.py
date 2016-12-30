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
import uuid
import pkg_resources
import sys
import platform
from builtins import str

from yandextank.common.exceptions import PluginNotPrepared
from yandextank.common.interfaces import GeneratorPlugin

from ..common.util import update_status, execute, pid_exists

from ..common.resource import manager as resource
from ..plugins.Aggregator import Plugin as AggregatorPlugin
from ..plugins.Monitoring import Plugin as MonitoringPlugin
from ..plugins.Telegraf import Plugin as TelegrafPlugin
if sys.version_info[0] < 3:
    import ConfigParser
else:
    import configparser as ConfigParser

logger = logging.getLogger(__name__)


class Job(object):
    def __init__(
            self,
            name,
            description,
            task,
            version,
            config_copy,
            monitoring_plugin,
            aggregator_plugin,
            tank,
            generator_plugin=None):
        # type: (unicode, unicode, unicode, unicode, unicode, MonitoringPlugin,
        # AggregatorPlugin, GeneratorPlugin) -> Job
        self.name = name
        self.description = description
        self.task = task
        self.version = version
        self.config_copy = config_copy
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


class TankCore(object):
    """
    JMeter + dstat inspired :)
    """
    SECTION = 'tank'
    SECTION_META = 'meta'
    PLUGIN_PREFIX = 'plugin_'
    PID_OPTION = 'pid'
    UUID_OPTION = 'uuid'
    LOCK_DIR = '/var/lock'

    def __init__(self, artifacts_base_dir=None, artifacts_dir_name=None):
        self.config = ConfigManager()
        self.status = {}
        self.plugins = []
        self.artifacts_dir_name = artifacts_dir_name
        self._artifacts_dir = None
        self.artifact_files = {}
        self.artifacts_base_dir = artifacts_base_dir
        self.manual_start = False
        self.scheduled_start = None
        self.interrupted = False
        self.lock_file = None
        self.flush_config_to = None
        self.lock_dir = None
        self.taskset_path = None
        self.taskset_affinity = None
        self.uuid = str(uuid.uuid4())
        self.set_option(self.SECTION, self.UUID_OPTION, self.uuid)
        self.set_option(self.SECTION, self.PID_OPTION, str(os.getpid()))
        self.job = None

    def get_uuid(self):
        return self.uuid

    def get_available_options(self):
        return [
            "artifacts_base_dir", "artifacts_dir", "flush_config_to",
            "taskset_path", "affinity"
        ]

    def load_configs(self, configs):
        """ Tells core to load configs set into options storage """
        logger.info("Loading configs...")
        self.config.load_files(configs)
        dotted_options = []
        for option, value in self.config.get_options(self.SECTION):
            if '.' in option:
                dotted_options += [option + '=' + value]
        self.apply_shorthand_options(dotted_options, self.SECTION)
        self.config.flush()
        self.add_artifact_file(self.config.file)
        self.set_option(self.SECTION, self.PID_OPTION, str(os.getpid()))
        self.flush_config_to = self.get_option(
            self.SECTION, "flush_config_to", "")
        if self.flush_config_to:
            self.config.flush(self.flush_config_to)

    def load_plugins(self):
        """
        Tells core to take plugin options and instantiate plugin classes
        """
        logger.info("Loading plugins...")

        if not self.artifacts_base_dir:
            self.artifacts_base_dir = os.path.expanduser(
                self.get_option(self.SECTION, "artifacts_base_dir", '.'))

        if not self.artifacts_dir_name:
            self.artifacts_dir_name = self.get_option(
                self.SECTION, "artifacts_dir", "")

        self.taskset_path = self.get_option(
            self.SECTION, 'taskset_path', 'taskset')
        self.taskset_affinity = self.get_option(self.SECTION, 'affinity', '')

        options = self.config.get_options(self.SECTION, self.PLUGIN_PREFIX)
        for (plugin_name, plugin_path) in options:
            if not plugin_path:
                logger.debug("Seems the plugin '%s' was disabled", plugin_name)
                continue
            logger.debug("Loading plugin %s from %s", plugin_name, plugin_path)
            # FIXME cleanup an old deprecated plugin path format
            if '/' in plugin_path:
                logger.warning(
                    "Deprecated plugin path format: %s\n"
                    "Should be in pythonic format. Example:\n"
                    "    plugin_jmeter=yandextank.plugins.JMeter", plugin_path)
                if plugin_path.startswith("Tank/Plugins/"):
                    plugin_path = "yandextank.plugins." + \
                                  plugin_path.split('/')[-1].split('.')[0]
                    logger.warning("Converted plugin path to %s", plugin_path)
                else:
                    raise ValueError(
                        "Couldn't convert plugin path to new format:\n    %s" %
                        plugin_path)
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
                instance = getattr(plugin, 'Plugin')(self)
            except:
                logger.warning(
                    "Deprecated plugin classname: %s. Should be 'Plugin'",
                    plugin)
                instance = getattr(
                    plugin, plugin_path.split('.')[-1] + 'Plugin')(self)

            self.plugins.append(instance)

        logger.debug("Plugin instances: %s", self.plugins)

    def plugins_configure(self):
        """        Call configure() on all plugins        """
        self.publish("core", "stage", "configure")
        if not os.path.exists(self.artifacts_base_dir):
            os.makedirs(self.artifacts_base_dir)

            os.chmod(self.artifacts_base_dir, 0o755)

        logger.info("Configuring plugins...")
        if self.taskset_affinity != '':
            self.taskset(os.getpid(), self.taskset_path, self.taskset_affinity)

        # monitoring plugin
        try:
            mon = self.get_plugin_of_type(TelegrafPlugin)
        except KeyError:
            logger.debug("Telegraf plugin not found:", exc_info=True)
            try:
                mon = self.get_plugin_of_type(MonitoringPlugin)
            except KeyError:
                logger.debug("Monitoring plugin not found:", exc_info=True)
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

        self.job = Job(
            name=self.get_option(self.SECTION_META, "job_name",
                                 'none').decode('utf8'),
            description=self.get_option(self.SECTION_META, "job_dsc",
                                        '').decode('utf8'),
            task=self.get_option(self.SECTION_META, 'task',
                                 'dir').decode('utf8'),
            version=self.get_option(self.SECTION_META, 'ver',
                                    '').decode('utf8'),
            config_copy=self.get_option(
                self.SECTION_META, 'copy_config_to', 'config_copy'),
            monitoring_plugin=mon,
            aggregator_plugin=aggregator,
            generator_plugin=gen,
            tank=socket.getfqdn())

        for plugin in self.plugins:
            logger.debug("Configuring %s", plugin)
            plugin.configure()
            self.config.flush()
        if self.flush_config_to:
            self.config.flush(self.flush_config_to)

    def plugins_prepare_test(self):
        """ Call prepare_test() on all plugins        """
        logger.info("Preparing test...")
        self.publish("core", "stage", "prepare")
        for plugin in self.plugins:
            logger.debug("Preparing %s", plugin)
            plugin.prepare_test()
        if self.flush_config_to:
            self.config.flush(self.flush_config_to)

    def plugins_start_test(self):
        """        Call start_test() on all plugins        """
        logger.info("Starting test...")
        self.publish("core", "stage", "start")
        for plugin in self.plugins:
            logger.debug("Starting %s", plugin)
            plugin.start_test()
        if self.flush_config_to:
            self.config.flush(self.flush_config_to)

    def wait_for_finish(self):
        """
        Call is_test_finished() on all plugins 'till one of them initiates exit
        """

        logger.info("Waiting for test to finish...")
        self.publish("core", "stage", "shoot")
        if not self.plugins:
            raise RuntimeError("It's strange: we have no plugins loaded...")

        while not self.interrupted:
            begin_time = time.time()
            for plugin in self.plugins:
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

        for plugin in self.plugins:
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

        if self.flush_config_to:
            self.config.flush(self.flush_config_to)
        return retcode

    def plugins_post_process(self, retcode):
        """
        Call post_process() on all plugins
        """
        logger.info("Post-processing test...")
        self.publish("core", "stage", "post_process")

        for plugin in self.plugins:
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

        if self.flush_config_to:
            self.config.flush(self.flush_config_to)

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
        """
        `Get` an option from option storage
        and `set` if default specified.
        """
        if not self.config.config.has_section(section):
            logger.debug("No section '%s', adding", section)
            self.config.config.add_section(section)

        try:
            value = self.config.config.get(section, option).strip()
        except ConfigParser.NoOptionError as ex:
            if default is not None:
                default = str(default)
                self.config.config.set(section, option, default)
                self.config.flush()
                value = default.strip()
            else:
                logger.warn(
                    "Mandatory option %s was not found in section %s", option,
                    section)
                raise ex

        if len(value) > 1 and value[0] == '`' and value[-1] == '`':
            logger.debug("Expanding shell option %s", value)
            retcode, stdout, stderr = execute(value[1:-1], True, 0.1, True)
            if retcode or stderr:
                raise ValueError(
                    "Error expanding option %s, RC: %s" % (value, retcode))
            value = stdout.strip()

        return value

    def set_option(self, section, option, value):
        """
        Set an option in storage
        """
        if not self.config.config.has_section(section):
            self.config.config.add_section(section)
        self.config.config.set(section, option, value)
        self.config.flush()

    def get_plugin_of_type(self, plugin_class):
        """
        Retrieve a plugin of desired class, KeyError raised otherwise
        """
        logger.debug("Searching for plugin: %s", plugin_class)
        matches = [
            plugin for plugin in self.plugins
            if isinstance(plugin, plugin_class)
        ]
        if len(matches) > 0:
            if len(matches) > 1:
                logger.debug(
                    "More then one plugin of type %s found. Using first one.",
                    plugin_class)
            return matches[-1]
        else:
            raise KeyError("Requested plugin type not found: %s" % plugin_class)

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
            try:
                section = option_str[:option_str.index('.')]
                option = option_str[option_str.index('.') + 1:option_str.index(
                    '=')]
            except ValueError:
                section = default_section
                option = option_str[:option_str.index('=')]
            value = option_str[option_str.index('=') + 1:]
            logger.debug(
                "Override option: %s => [%s] %s=%s", option_str, section,
                option, value)
            self.set_option(section, option, value)

    def get_lock_dir(self):
        if not self.lock_dir:
            self.lock_dir = self.get_option(
                self.SECTION, "lock_dir", self.LOCK_DIR)

        return os.path.expanduser(self.lock_dir)

    def get_lock(self, force=False):
        if not force and self.__there_is_locks():
            raise RuntimeError("There is lock files")

        fh, self.lock_file = tempfile.mkstemp(
            '.lock', 'lunapark_', self.get_lock_dir())
        os.close(fh)
        os.chmod(self.lock_file, 0o644)
        self.config.file = self.lock_file
        self.config.flush()

    def release_lock(self):
        self.config.file = None
        if self.lock_file and os.path.exists(self.lock_file):
            logger.debug("Releasing lock: %s", self.lock_file)
            os.remove(self.lock_file)

    def __there_is_locks(self):
        retcode = False
        lock_dir = self.get_lock_dir()
        for filename in os.listdir(lock_dir):
            if fnmatch.fnmatch(filename, 'lunapark_*.lock'):
                full_name = os.path.join(lock_dir, filename)
                logger.warn("Lock file present: %s", full_name)

                try:
                    info = ConfigParser.ConfigParser()
                    info.read(full_name)
                    pid = info.get(TankCore.SECTION, self.PID_OPTION)
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

        for plugin in self.plugins:
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
            if not self.artifacts_dir_name:
                date_str = datetime.datetime.now().strftime(
                    "%Y-%m-%d_%H-%M-%S.")
                self.artifacts_dir_name = tempfile.mkdtemp(
                    "", date_str, self.artifacts_base_dir)
            elif not os.path.isdir(self.artifacts_dir_name):
                os.makedirs(self.artifacts_dir_name)
            os.chmod(self.artifacts_dir_name, 0o755)
            self._artifacts_dir = os.path.abspath(self.artifacts_dir_name)
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


class ConfigManager(object):
    """ Option storage class """

    def __init__(self):
        self.file = None
        self.config = ConfigParser.ConfigParser()

    def load_files(self, configs):
        """         Read configs set into storage        """
        logger.debug("Reading configs: %s", configs)
        config_filenames = [
            resource.resource_filename(config) for config in configs
        ]
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
