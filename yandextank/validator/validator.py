import importlib
import os
import re
import sys
import uuid

import logging

import glob
import pkg_resources
import yaml
from cerberus.validator import Validator
from functools import reduce

from yandextank.common.util import read_resource, recursive_dict_update
logger = logging.getLogger(__name__)


class ValidationError(Exception):
    MSG_TEMPLATE = """Validation error:\n{}"""

    def __init__(self, errors):
        self.errors = errors
        self.message = self.MSG_TEMPLATE.format(yaml.dump(self.errors))

    def __str__(self):
        return self.message


def load_yaml_schema(path):
    # DEFAULT_FILENAME = 'schema.yaml'
    file_content = read_resource(path)
    return yaml.safe_load(file_content)


def load_py_schema(package):
    schema_module = importlib.import_module(package + '.config.schema')
    return schema_module.SCHEMA


def load_plugin_schema(package):
    try:
        return load_yaml_schema(
            pkg_resources.resource_filename(
                package, 'config/schema.yaml'))
    except IOError:
        try:
            return load_py_schema(package)
        except ImportError:
            logger.error(
                "Could not find schema for %s (should be located in config/ directory of a plugin)",
                package)
            raise IOError('No schema found for plugin %s' % package)
    except ImportError:
        if 'aggregator' in package.lower():
            logger.exception('Plugin Aggregator is now deprecated, please remove this section from your config.')
        raise ValidationError({'package': ['No module named {}'.format(package)]})


def load_schema(directory, filename=None):
    try:
        return load_yaml_schema(directory)
    except IOError:
        try:
            return load_py_schema(directory)
        except ImportError:
            raise IOError(
                'Neither .yaml nor .py schema found in %s' %
                directory)


class PatchedValidator(Validator):

    def _validate_description(self, description, field, value):
        """ {'type': 'string'} """
        pass

    def _validate_values_description(self, values_description, field, value):
        """ {'type': 'dict'} """
        pass

    def _validate_tutorial_link(self, tutorial_link, field, value):
        """ {'type': 'string'} """
        pass

    def _validate_examples(self, examples, field, value):
        """ {'type': 'dict'} """
        pass

    @staticmethod
    def is_number(value):
        try:
            float(value)
            return True
        except ValueError:
            return False

    def validate_duration(self, field, duration):
        '''
        2h
        2h5m
        5m
        180
        1h4m3
        :param duration:
        :return:
        '''
        DURATION_RE = r'^(\d+d)?(\d+h)?(\d+m)?(\d+s?)?$'
        if not re.match(DURATION_RE, duration):
            self._error(field, 'Load duration examples: 2h30m; 5m15; 180')

    def _check_with_load_scheme(self, field, value):
        '''
        step(10,200,5,180)
        step(5,50,2.5,5m)
        line(22,154,2h5m)
        step(5,50,2.5,5m) line(22,154,2h5m)
        const(10,1h4m3s)
        :param field:
        :param value:
        :return:
        '''
        # stpd file can be any value
        if self.document['load_type'] in 'stpd_file':
            return

        PRIMARY_RE = r'(step|line|const)\((.+?)\)'
        N_OF_ARGS = {
            'step': 4,
            'line': 3,
            'const': 2,
        }
        matches = re.findall(PRIMARY_RE, value)
        if len(matches) == 0:
            self._error(field, 'Should match one of the following patterns: step(...) / line(...) / const(...)')
        else:
            for match in matches:
                curve, params_str = match
                params = [v.strip() for v in params_str.split(',')]
                # check number of arguments
                if not len(params) == N_OF_ARGS[curve]:
                    self._error(field, '{} load scheme: expected {} arguments, found {}'.format(curve,
                                                                                                N_OF_ARGS[curve],
                                                                                                len(params)))
                # check arguments' types
                for param in params[:-1]:
                    if not self.is_number(param):
                        self._error(field, 'Argument {} in load scheme should be a number'.format(param))
                self.validate_duration(field, params[-1])


class TankConfig(object):
    DYNAMIC_OPTIONS = {
        'uuid': lambda: str(uuid.uuid4()),
        'pid': lambda: os.getpid(),
        'cmdline': lambda: ' '.join(sys.argv)
    }

    def __init__(
            self,
            configs,
            with_dynamic_options=True,
            core_section='core',
            error_output=None,
            skip_base_cfgs=True,
    ):
        """
        :param configs: list of configs dicts
        :param with_dynamic_options: insert uuid, pid, and other DYNAMIC_OPTIONS
        :param core_section: name of core section in config
        :param error_output: file to output error messages
        """
        if not isinstance(configs, list):
            configs = [configs]
        self.raw_config_dict = self.__construct_config(configs, skip_base_cfgs)
        if self.raw_config_dict.get(core_section) is None:
            self.raw_config_dict[core_section] = {}
        self.with_dynamic_options = with_dynamic_options
        self.CORE_SECTION = core_section
        self._validated = None
        self._plugins = None
        self.ERROR_OUTPUT = error_output
        self.BASE_SCHEMA = load_yaml_schema(pkg_resources.resource_filename('yandextank.core', 'config/schema.yaml'))
        self.PLUGINS_SCHEMA = load_yaml_schema(pkg_resources.resource_filename('yandextank.core', 'config/plugins_schema.yaml'))

    def get_configinitial(self):
        return self.raw_config_dict

    def validate(self):
        if not self._validated:
            self._validated = ValidatedConfig(self.__validate(), self.BASE_SCHEMA)
        return self._validated, self.raw_config_dict

    @property
    def validated(self):
        if not self._validated:
            try:
                self._validated = self.__validate()
            except ValidationError as e:
                if self.ERROR_OUTPUT:
                    with open(self.ERROR_OUTPUT, 'w') as f:
                        yaml.dump(e.errors, f)
                raise
        return self._validated

    def save_raw(self, filename):
        with open(filename, 'w') as f:
            yaml.dump(self.raw_config_dict, f)

    def __construct_config(self, user_configs, skip_base_cfgs):
        user_config = self.__merge_configs(user_configs)
        if skip_base_cfgs:
            return user_config

        # YANDEXTANK-715: for backward compatibility purposes
        user_config = self.__patch_phantom_implicit_enabled_true(user_config)
        configs = [load_core_base_cfg()] + load_local_base_cfgs() + [user_config]
        config = self.__merge_configs(configs)
        return config

    @staticmethod
    def __merge_configs(configs):
        logger.info('Configs: {}'.format(configs))
        configs = list(filter(None, configs))
        return reduce(recursive_dict_update, configs, {})

    @staticmethod
    def __patch_phantom_implicit_enabled_true(user_cfg):
        if not (phantom_section := user_cfg.get('phantom', {})):
            return user_cfg
        if not phantom_section.get('enabled', True):
            return user_cfg
        user_cfg['phantom']['enabled'] = True
        return user_cfg

    def __parse_enabled_plugins(self):
        """
        :returns: [(plugin_name, plugin_package, plugin_config), ...]
        :rtype: list of tuple
        """
        return [
            (
                plugin_name,
                plugin['package'],
                plugin) for plugin_name,
            plugin in self.raw_config_dict.items() if (
                plugin_name not in self.BASE_SCHEMA) and isinstance(
                plugin,
                dict) and plugin.get('enabled')]

    def __validate(self):
        core_validated = self.__validate_core()
        # plugins:
        errors = {}
        results = {}
        for plugin_name, package, config in self.__parse_enabled_plugins():
            try:
                results[plugin_name] = \
                    self.__validate_plugin(config,
                                           load_plugin_schema(package))
            except ValidationError as e:
                errors[plugin_name] = e.errors
        if len(errors) > 0:
            raise ValidationError(dict(errors))

        for plugin_name, plugin_conf in results.items():
            core_validated[plugin_name] = plugin_conf
        return core_validated

    def __validate_core(self):
        v = PatchedValidator(allow_unknown=self.PLUGINS_SCHEMA)
        result = v.validate(self.raw_config_dict, self.BASE_SCHEMA)
        if not result:
            errors = v.errors
            for key, value in tuple(errors.items()):
                if 'must be of dict type' in value:
                    errors[key] = ['unknown field']
            raise ValidationError(errors)
        normalized = v.normalized(self.raw_config_dict)
        return self.__set_core_dynamic_options(
            normalized) if self.with_dynamic_options else normalized

    def __validate_plugin(self, config, schema):
        schema.update(self.PLUGINS_SCHEMA['schema'])
        v = PatchedValidator(schema, allow_unknown=False)
        # .validate() makes .errors as side effect if there's any
        if not v.validate(config):
            raise ValidationError(v.errors)
        # .normalized() returns config with defaults
        return v.normalized(config)

    def __set_core_dynamic_options(self, config):
        for option, setter in self.DYNAMIC_OPTIONS.items():
            try:
                config[self.CORE_SECTION][option] = setter()
            except KeyError:
                config[self.CORE_SECTION] = {option: setter()}
        return config

    def __str__(self):
        return yaml.dump(self.raw_config_dict)


class ValidatedConfig(object):
    def __init__(self, validated, base_schema):
        """

        :type validated: dict
        """
        self.validated = validated
        self.base_schema = base_schema
        self._plugins = None

    @property
    def plugins(self):
        """
            :returns: [(plugin_name, plugin_package, plugin_config), ...]
            :rtype: list of tuple
        """
        if not self._plugins:
            self._plugins = [
                (plugin_name,
                 plugin_cfg['package'],
                 plugin_cfg) for plugin_name, plugin_cfg in self.validated.items() if (
                    plugin_name not in self.base_schema) and plugin_cfg['enabled']]
        return self._plugins

    def get_option(self, section, option, default=None):
        try:
            return self.validated[section][option]
        except KeyError:
            if default is not None:
                return default
            raise

    def __bool__(self):
        return len(self.validated) > 0

    def dump(self, path):
        with open(path, 'w') as f:
            yaml.dump(self.validated, f)

    def __str__(self):
        return yaml.dump(self.validated)


def load_core_base_cfg():
    return load_yaml_cfg(pkg_resources.resource_filename('yandextank.core', 'config/00-base.yaml'))


def load_local_base_cfgs():
    return cfg_folder_loader('/etc/yandex-tank')


def cfg_folder_loader(path):
    """
    :type path: str
    """
    CFG_WILDCARD = '*.yaml'
    return [load_yaml_cfg(filename) for filename in sorted(glob.glob(os.path.join(path, CFG_WILDCARD)))]


def load_yaml_cfg(cfg_filename):
    """
    :type cfg_filename: str
    """
    cfg_yaml = yaml.load(read_resource(cfg_filename), Loader=yaml.FullLoader)
    if not isinstance(cfg_yaml, dict):
        raise ValidationError('Wrong config format, should be a yaml')
    return cfg_yaml
