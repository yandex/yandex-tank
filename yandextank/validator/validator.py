import imp
import os
import sys
import uuid

import logging
import pkg_resources
import yaml
from cerberus.validator import Validator, InspectedValidator

from yandextank.common.util import recursive_dict_update
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
    with open(path, 'r') as f:
        return yaml.load(f)


def load_py_schema(path):
    schema_module = imp.load_source('schema', path)
    return schema_module.SCHEMA


def load_plugin_schema(package):
    try:
        return load_yaml_schema(pkg_resources.resource_filename(package, 'config/schema.yaml'))
    except IOError:
        try:
            return load_py_schema(pkg_resources.resource_filename(package, 'config/schema.py'))
        except ImportError:
            logger.error("Could not find schema for %s (should be located in config/ directory of a plugin)", package)
            raise IOError('No schema found for plugin %s' % package)


def load_schema(directory, filename=None):
    try:
        return load_yaml_schema(directory)
    except IOError:
        try:
            return load_py_schema(directory)
        except ImportError:
            raise IOError('Neither .yaml nor .py schema found in %s' % directory)


class TankConfig(object):
    DYNAMIC_OPTIONS = {
        'uuid': lambda: str(uuid.uuid4()),
        'pid': lambda: os.getpid(),
        'cmdline': lambda: ' '.join(sys.argv)
    }

    def __init__(self, configs, with_dynamic_options=True, core_section='core', error_output='validation_error.yaml'):
        self._errors = None
        if not isinstance(configs, list):
            configs = [configs]
        self.raw_config_dict = self.__load_multiple([config for config in configs if config is not None])
        self.with_dynamic_options = with_dynamic_options
        self.CORE_SECTION = core_section
        self._validated = None
        self._plugins = None
        self.ERROR_OUTPUT = error_output
        self.BASE_SCHEMA = load_yaml_schema(pkg_resources.resource_filename('yandextank.core', 'config/schema.yaml'))
        self.PLUGINS_SCHEMA = load_yaml_schema(pkg_resources.resource_filename('yandextank.core', 'config/plugins_schema.yaml'))

    def get_option(self, section, option):
        return self.validated[section][option]

    def has_option(self, section, option):
        return self.validated

    @property
    def plugins(self):
        """
            :returns: [(plugin_name, plugin_package, plugin_config), ...]
            :rtype: list of tuple
        """
        if not self._plugins:
            self._plugins = [(plugin_name, plugin_cfg['package'], plugin_cfg, self.__get_cfg_updater(plugin_name))
                             for plugin_name, plugin_cfg in self.validated.items()
                             if (plugin_name not in self.BASE_SCHEMA.keys()) and plugin_cfg['enabled']]
        return self._plugins

    @property
    def validated(self):
        if not self._validated:
            try:
                self._validated = self.__validate()
            except ValidationError as e:
                with open(self.ERROR_OUTPUT, 'w') as f:
                    yaml.dump(e.errors, f)
                raise
        return self._validated

    def save(self, filename, error_message=''):
        with open(filename, 'w') as f:
            yaml.dump(
                self.__load_multiple(
                    [self.validated,
                     {self.CORE_SECTION: {'message': error_message}}]
                ), f)

    def save_raw(self, filename):
        with open(filename, 'w') as f:
            yaml.dump(self.raw_config_dict, f)

    def __load_multiple(self, configs):
        l = len(configs)
        if l == 0:
            return {}
        elif l == 1:
            return configs[0]
        elif l == 2:
            return recursive_dict_update(configs[0], configs[1])
        else:
            return self.__load_multiple([recursive_dict_update(configs[0], configs[1])] + configs[2:])

    def __parse_enabled_plugins(self):
        """
        :returns: [(plugin_name, plugin_package, plugin_config), ...]
        :rtype: list of tuple
        """
        return [(plugin_name, plugin['package'], plugin)
                for plugin_name, plugin in self.raw_config_dict.items()
                if (plugin_name not in self.BASE_SCHEMA.keys()) and isinstance(plugin, dict) and plugin.get('enabled')]

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
            raise ValidationError((dict(errors)))

        for plugin_name, plugin_conf in results.items():
            core_validated[plugin_name] = plugin_conf
        return core_validated

    def __validate_core(self):
        # monkey-patch to allow description field
        def _validate_description(self, description, field, value):
            """ {'type': 'string'} """
            pass

        Validator._validate_description = _validate_description
        MyValidator = InspectedValidator('Validator', (Validator,), {})

        v = MyValidator(allow_unknown=self.PLUGINS_SCHEMA)
        result = v.validate(self.raw_config_dict, self.BASE_SCHEMA)
        if not result:
            errors = v.errors
            for key, value in v.errors.items():
                if 'must be of dict type' in value:
                    errors[key] = ['unknown field']
            raise ValidationError(errors)
        normalized = v.normalized(self.raw_config_dict)
        return self.__set_core_dynamic_options(normalized) if self.with_dynamic_options else normalized

    def __validate_plugin(self, config, schema):
        schema.update(self.PLUGINS_SCHEMA['schema'])
        v = Validator(schema, allow_unknown=False)
        # .validate() makes .errors as side effect if there's any
        if not v.validate(config):
            raise ValidationError(v.errors)
        # .normalized() returns config with defaults
        return v.normalized(config)

    def __set_core_dynamic_options(self, config):
        for option, setter in self.DYNAMIC_OPTIONS.items():
            config[self.CORE_SECTION][option] = setter()
        return config

    def __get_cfg_updater(self, plugin_name):
        def cfg_updater(key, value):
            self.validated[plugin_name][key] = value
        return cfg_updater

    def __str__(self):
        return yaml.dump(self.validated)

    def errors(self):
        if not self._errors:
            try:
                self.validated
            except ValidationError as e:
                self._errors = e.errors
            else:
                self._errors = []
        return self._errors
