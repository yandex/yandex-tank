import collections
import importlib
import os
import pkgutil
import sys
import uuid

import yaml
from cerberus import Validator

TANK_DIR = os.path.dirname(os.path.dirname(importlib.import_module('yandextank').__file__))


class ValidationError(Exception):
    pass


def load_yaml_schema(directory, filename=None):
    DEFAULT_FILENAME = 'schema.yaml'
    name = filename if filename else DEFAULT_FILENAME
    with open(os.path.join(directory, name), 'r') as f:
        return yaml.load(f)


def load_py(directory, filename=None):
    DEFAULT_PY_MODULE_NAME = 'schema'
    name = filename if filename else DEFAULT_PY_MODULE_NAME
    path = os.path.join(directory, name)
    schema_module = importlib.import_module(os.path.relpath(path, TANK_DIR).replace('/', '.'))
    return schema_module.SCHEMA


def load_schema(directory, filename=None):
    try:
        return load_yaml_schema(directory, filename)
    except IOError:
        try:
            return load_py(directory, filename)
        except ImportError:
            raise IOError('Neither .yaml nor .py schema found in %s' % directory)


class TankConfig(object):

    def __init__(self, configs, with_dynamic_options=True):
        if not isinstance(configs, list):
            configs = [configs]
        self.__raw_config_dict = self.__load_multiple(configs)
        self.with_dynamic_options = with_dynamic_options
        self._validated = None
        self._plugins = None
        self.BASE_SCHEMA = load_schema(os.path.join(os.path.dirname(__file__), '../core/'))
        self.PLUGIN_SCHEMA = load_schema(os.path.join(os.path.dirname(__file__), '../core/'), filename='plugins_schema.yaml')

    def get_option(self, section, option):
        return self.validated[section][option]

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
            self._validated = self.__validate()
        return self._validated

    def save(self, filename):
        with open(filename, 'w') as f:
            yaml.dump(self.validated, f)

    def __load_multiple(self, configs):
        l = len(configs)
        if l == 0:
            return {}
        elif l == 1:
            return configs[0]
        elif l == 2:
            return self.__recursive_update(configs[0], configs[1])
        else:
            return self.__load_multiple([self.__recursive_update(configs[0], configs[1])] + configs[2:])

    def __parse_enabled_plugins(self):
        """
        :returns: [(plugin_name, plugin_package, plugin_config), ...]
        :rtype: list of tuple
        """
        return [(plugin_name, plugin['package'], plugin)
                for plugin_name, plugin in self.__raw_config_dict.items()
                if (plugin_name not in self.BASE_SCHEMA.keys()) and plugin['enabled']]

    def __validate(self):
        core_validated = self.__validate_core()
        # plugins:
        errors = {}
        results = {}
        for plugin_name, package, config in self.__parse_enabled_plugins():
            try:
                results[plugin_name] = \
                    self.__validate_plugin(config,
                                           load_schema(pkgutil.get_loader(package).filename))
            except ValidationError as e:
                errors[plugin_name] = e.message
        if len(errors) > 0:
            raise ValidationError(dict(errors))

        for plugin_name, plugin_conf in results.items():
            core_validated[plugin_name] = plugin_conf
        return core_validated

    def __validate_core(self):
        v = Validator(self.BASE_SCHEMA, allow_unknown=self.PLUGIN_SCHEMA)
        result = v.validate(self.__raw_config_dict, self.BASE_SCHEMA)
        if not result:
            raise ValidationError(v.errors)
        normalized = v.normalized(self.__raw_config_dict)
        return self.__set_core_dynamic_options(normalized) if self.with_dynamic_options else normalized

    def __validate_plugin(self, config, schema=None):
        if not schema:
            schema = load_schema(pkgutil.get_loader(config['package']).filename)
        schema.update(self.PLUGIN_SCHEMA['schema'])
        v = Validator(schema, allow_unknown=False)
        # .validate() makes .errors as side effect if there's any
        if not v.validate(config):
            raise ValidationError(v.errors)
        # .normalized() returns config with defaults
        return v.normalized(config)

    def __recursive_update(self, d, u):
        for k, v in u.items():
            if isinstance(v, collections.Mapping):
                r = self.__recursive_update(d.get(k, {}), v)
                d[k] = r
            else:
                d[k] = u[k]
        return d

    def __set_core_dynamic_options(self, config):
        META_LOCATION = 'core'
        config[META_LOCATION]['uuid'] = str(uuid.uuid4())
        config[META_LOCATION]['pid'] = os.getpid()
        config[META_LOCATION]['cmdline'] = ' '.join(sys.argv)
        return config

    def __get_cfg_updater(self, plugin_name):
        def cfg_updater(key, value):
            self.validated[plugin_name][key] = value
        return cfg_updater

    def __str__(self):
        return yaml.dump(self.validated)
