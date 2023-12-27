# TODO: merge with Yandex Tank validator
import yaml
import pkg_resources
import logging
import importlib.util

from cerberus import Validator
from yandextank.contrib.netort.netort.data_manager.common.util import recursive_dict_update


logger = logging.getLogger(__name__)


class ValidationError(Exception):
    pass


def load_yaml_schema(path):
    with open(path) as f:
        return yaml.load(f)


def load_py_schema(path):
    spec = importlib.util.spec_from_file_location('schema', path)
    schema_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(schema_module)
    return schema_module.SCHEMA


def load_schema(directory):
    try:
        return load_yaml_schema(directory)
    except IOError:
        try:
            return load_py_schema(directory)
        except ImportError:
            raise IOError('Neither .yaml nor .py schema found in %s' % directory)


class ValidatedConfig(object):
    def __init__(
            self,
            configs,
            dynamic_options,
            package_schema_path,
            package_schema_file='config/schema.yaml',
            with_dynamic_options=True,
            core_section='core'
    ):
        if not isinstance(configs, list):
            configs = [configs]
        self.__raw_config_dict = self.__load_multiple(
            [config for config in configs if config is not None])
        if self.__raw_config_dict.get(core_section) is None:
            self.__raw_config_dict[core_section] = {}
        self.BASE_SCHEMA = load_yaml_schema(
            pkg_resources.resource_filename(
                package_schema_path, package_schema_file
            )
        )
        self.DYNAMIC_OPTIONS = dynamic_options
        self.CORE_SECTION = core_section
        self._validated = None
        self.with_dynamic_options = with_dynamic_options
        logger.debug('patched_raw_config_dict: %s', self.__raw_config_dict)

    def __load_multiple(self, configs):
        configs_count = len(configs)
        if configs_count == 0:
            return {}
        elif configs_count == 1:
            return configs[0]
        elif configs_count == 2:
            return recursive_dict_update(configs[0], configs[1])
        else:
            return self.__load_multiple(
                [recursive_dict_update(configs[0], configs[1])] + configs[2:])

    def get_option(self, section, option, default=None):
        try:
            self.validated[section][option]
        except KeyError:
            if default is not None:
                return default
            else:
                raise KeyError()
        return self.validated[section][option]

    def get_enabled_sections(self):
        return [
            section_name for section_name, section_config in self.__raw_config_dict.items()
            if section_config.get('enabled', False)
        ]

    def has_option(self, section, option):
        return self.validated

    @property
    def validated(self):
        if not self._validated:
            self._validated = self.__validate()
        return self._validated

    def save(self, filename):
        with open(filename, 'w') as f:
            yaml.dump(self.validated, f)

    def __validate(self):
        core_validated = self.__validate_core()
        errors = {}
        if len(errors) > 0:
            raise ValidationError(dict(errors))
        return core_validated

    def __validate_core(self):
        v = Validator(self.BASE_SCHEMA)
        result = v.validate(self.__raw_config_dict, self.BASE_SCHEMA)
        if not result:
            raise ValidationError(v.errors)
        normalized = v.normalized(self.__raw_config_dict)
        return self.__set_core_dynamic_options(normalized) if self.with_dynamic_options else normalized

    def __set_core_dynamic_options(self, config):
        for option, setter in self.DYNAMIC_OPTIONS.items():
            config[self.CORE_SECTION][option] = setter()
        return config
