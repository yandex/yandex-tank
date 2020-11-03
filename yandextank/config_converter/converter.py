import logging
import re
from configparser import RawConfigParser, ParsingError
from functools import reduce

import pkg_resources
import yaml

from yandextank.common.util import recursive_dict_update
from yandextank.validator.validator import load_plugin_schema, load_yaml_schema

logger = logging.getLogger(__name__)
CORE_SCHEMA = load_yaml_schema(pkg_resources.resource_filename('yandextank.core', 'config/schema.yaml'))['core']['schema']

DEPRECATED_SECTIONS = ['lunaport', 'aggregator']


def old_plugin_mapper(package):
    MAP = {'Overload': 'DataUploader'}
    return MAP.get(package, package)


def parse_package_name(package_path):
    if package_path.startswith("Tank/Plugins/"):
        package = package_path.split('/')[-1].split('.')[0]
    else:
        package = package_path.split('.')[-1].split()[0]
    return old_plugin_mapper(package)


SECTIONS_PATTERNS = {
    'tank': 'core|tank',
    'Aggregator': 'aggregator',
    'Android': 'android',
    'Appium': 'appium',
    'Autostop': 'autostop',
    'BatteryHistorian': 'battery_historian',
    'Bfg': 'bfg|ultimate_gun|http_gun|custom_gun|scenario_gun',
    'Phantom': 'phantom(-.*)?',
    'DataUploader': 'meta|overload|uploader|datauploader',
    'Telegraf': 'telegraf|monitoring',
    'JMeter': 'jmeter',
    'ResourceCheck': 'rcheck',
    'ShellExec': 'shell_?exec',
    'ShootExec': 'shoot_?exec',
    'Console': 'console',
    'TipsAndTricks': 'tips',
    'RCAssert': 'rcassert',
    'JsonReport': 'json_report|jsonreport',
    'Pandora': 'pandora',
    'InfluxUploader': 'influx',
    'OpenTSDBUploader': 'opentsdb',

}


class ConversionError(Exception):
    MSG = 'ConversionError:\n{}\nCheck your file format'

    def __init__(self, message=''):
        self.message = self.MSG.format(message)


class OptionsConflict(ConversionError):
    pass


class UnrecognizedSection(ConversionError):
    pass


def guess_plugin(section):
    for plugin, section_name_pattern in SECTIONS_PATTERNS.items():
        if re.match(section_name_pattern, section):
            return plugin
    else:
        raise UnrecognizedSection('Section {} did not match any plugin'.format(section))


def convert_rps_schedule(key, value):
    return {'load_profile': {
        'load_type': 'rps',
        'schedule': value
    }}


def convert_instances_schedule(key, value):
    return {'load_profile': {
        'load_type': 'instances',
        'schedule': value
    }}


def convert_stpd_schedule(key, value):
    return {'load_profile': {
        'load_type': 'stpd_file',
        'schedule': value
    }}


def to_bool(value):
    try:
        return bool(int(value))
    except ValueError:
        return True if 'true' == value.lower() else False


def is_option_deprecated(plugin, option_name):
    DEPRECATED = {
        'Aggregator': [
            'time_periods',
            'precise_cumulative'
        ],
        'DataUploader': [
            'copy_config_to'
        ]
    }
    if option_name in DEPRECATED.get(plugin, []):
        logger.warning('Deprecated option {} in plugin {}, omitting'.format(option_name, plugin))
        return True
    else:
        return False


def check_options(plugin, options):
    CONFLICT_OPTS = {
        'Phantom': [{'rps_schedule', 'instances_schedule', 'stpd_file'}]
    }
    for conflict_options in CONFLICT_OPTS.get(plugin, []):
        intersect = {option[0] for option in options} & conflict_options
        if len(intersect) > 1:
            raise OptionsConflict('Conflicting options: {}: {}'.format(plugin, list(intersect)))
    return plugin, options


def without_deprecated(plugin, options):
    """
    :type options: list of tuple
    """
    return filter(lambda option: not is_option_deprecated(plugin, option[0]), options)


def old_section_name_mapper(name):
    MAP = {
        'monitoring': 'telegraf',
    }
    return MAP.get(name, name)


def rename(name):
    MAP = {
        'meta': 'uploader'
    }
    return MAP.get(name, name)


class Package(object):
    def __init__(self, package_path):
        if package_path.startswith("Tank/Plugins/"):
            self.package = package_path.split('.')[0].replace('Tank/Plugins/', 'yandextank.plugins.')
        else:
            self.package = package_path
        self.plugin_name = old_plugin_mapper(self.package.split('.')[-1])


class UnknownOption(ConversionError):

    def __init__(self, option):
        self.message = 'Unknown option: {}'.format(option)


def empty_to_none(func):
    def new_func(k, v):
        if v in '':
            return {k: None}
        else:
            return func(k, v)
    return new_func


class Option(object):
    TYPE_CASTERS = {
        'boolean': empty_to_none(lambda k, v: {k: to_bool(v)}),
        'integer': empty_to_none(lambda k, v: {k: int(v)}),
        'list': empty_to_none(lambda k, v: {k: [_.strip() for _ in v.strip().split()]}),
        'float': empty_to_none(lambda k, v: {k: float(v)})
    }

    SPECIAL_CONVERTERS = {
        'Phantom': {
            'rps_schedule': convert_rps_schedule,
            'instances_schedule': convert_instances_schedule,
            'stpd_file': convert_stpd_schedule,
            'autocases': TYPE_CASTERS['integer'],
            'headers': lambda key, value: {key: re.compile(r'\[(.*?)\]').findall(value)}
        },
        'Bfg': {
            'rps_schedule': convert_rps_schedule,
            'instances_schedule': convert_instances_schedule,
            'headers': lambda key, value: {key: re.compile(r'\[(.*?)\]').findall(value)}
        },
        'JMeter': {
            'exclude_markers': lambda key, value: {key: value.strip().split(' ')}
        },
        'Pandora': {
            'config_content': lambda key, value: {key: yaml.load(value, Loader=yaml.FullLoader)}  # works for json as well
        },
        'Autostop': {
            'autostop': lambda k, v: {k: re.findall(r'\w+\(.+?\)', v)}
        },
        'DataUploader': {
            'lock_targets': lambda k, v: {k: v.strip().split() if v != 'auto' else v}
        },
        'core': {
            'ignore_locks': lambda k, v: {'ignore_lock': to_bool(v)}
        }
    }
    CONVERTERS_FOR_UNKNOWN = {
        'DataUploader': lambda k, v: {'meta': {k: v}},
        'JMeter': lambda k, v: {'variables': {k: v}}
    }

    def __init__(self, plugin_name, key, value, schema=None):
        self.dummy_converter = lambda k, v: {k: v}
        self.plugin = plugin_name
        self._schema = schema

        if '.' in key:
            self.name, rest = key.split('.', 1)
            self.value = Option(plugin_name, rest, value, schema=self.schema[self.name]).converted
            self._converter = self.dummy_converter
        else:
            self.name = key
            self.value = value
            self._converter = None
        self._converted = None
        self._as_tuple = None

    @property
    def schema(self):
        if self._schema is None:
            module_paths = {
                'tank': 'yandextank.core'
            }

            def default_path(plugin):
                'yandextank.plugins.{}'.format(plugin)

            self._schema = load_plugin_schema(module_paths.get(self.plugin, default_path(self.plugin)))
        return self._schema

    @property
    def converted(self):
        """
        :rtype: {str: object}
        """
        if self._converted is None:
            self._converted = self.converter(self.name, self.value)
        return self._converted

    @property
    def as_tuple(self):
        """
        :rtype: (str, object)
        """
        if self._as_tuple is None:
            self._as_tuple = next(iter(self.converted.items()))
        return self._as_tuple

    @property
    def converter(self):
        """
        :rtype: callable
        """
        if self._converter is None:
            try:
                self._converter = self.SPECIAL_CONVERTERS[self.plugin][self.name]
            except KeyError:
                try:
                    self._converter = self._get_scheme_converter()
                except UnknownOption:
                    self._converter = self.CONVERTERS_FOR_UNKNOWN.get(self.plugin, self.dummy_converter)
        return self._converter

    def _get_scheme_converter(self):
        if self.name == 'enabled':
            return self.TYPE_CASTERS['boolean']
        if self.schema.get(self.name) is None:
            logger.warning('Unknown option {}:{}'.format(self.plugin, self.name))
            raise UnknownOption('{}:{}'.format(self.plugin, self.name))

        _type = self.schema[self.name].get('type', None)
        if _type is None:
            logger.warning('Option {}:{}: no type specified in schema'.format(self.plugin, self.name))
            return self.dummy_converter

        return self.TYPE_CASTERS.get(_type, self.dummy_converter)


class Section(object):
    def __init__(self, name, plugin, options, enabled=None):
        self.name = old_section_name_mapper(name)
        self.new_name = rename(self.name)
        self.plugin = plugin
        self._schema = None
        self.options = [Option(plugin, *option, schema=self.schema) for option in without_deprecated(*check_options(plugin, options))]
        self.enabled = enabled
        self._merged_options = None

    @property
    def schema(self):
        if self._schema is None:
            self._schema = load_plugin_schema('yandextank.plugins.' + self.plugin)
        return self._schema

    def get_cfg_dict(self, with_meta=True):
        options_dict = self.merged_options
        if with_meta:
            if self.plugin:
                options_dict.update({'package': 'yandextank.plugins.{}'.format(self.plugin)})
            if self.enabled is not None:
                options_dict.update({'enabled': self.enabled})
        return options_dict

    @property
    def merged_options(self):
        if self._merged_options is None:
            self._merged_options = reduce(lambda acc, upd: recursive_dict_update(acc, upd),
                                          [opt.converted for opt in self.options],
                                          {})
        return self._merged_options

    @classmethod
    def from_multiple(cls, sections, parent_name=None, child_name=None, is_list=True):
        """
        :type parent_name: str
        :type sections: list of Section
        """
        if len(sections) == 1:
            return sections[0]
        if parent_name:
            master_section = next(filter(lambda section: section.name == parent_name, sections))
            rest = filter(lambda section: section is not master_section, sections)
        else:
            master_section = sections[0]
            parent_name = master_section.name
            rest = sections[1:]
        child = {'multi': [section.get_cfg_dict(with_meta=False) for section in rest]} if is_list \
            else {child_name: cls._select_one(master_section, rest).get_cfg_dict(with_meta=False)}
        master_section.merged_options.update(child)
        return master_section

    def __repr__(self):
        return '{}/{}'.format(self.name, self.plugin)

    @classmethod
    def _select_one(cls, master_section, rest):
        MAP = {
            'bfg': lambda section: section.name == '{}_gun'.format(master_section.get_cfg_dict()['gun_type'])
        }
        return next(filter(MAP.get(master_section.name, lambda x: True), rest))
        # return filter(lambda section: section.name == MAP.get(master_section.name, ), rest)[0]


def without_defaults(cfg_ini, section):
    """

    :rtype: (str, str)
    :type cfg_ini: ConfigParser
    """
    defaults = cfg_ini.defaults()
    options = cfg_ini.items(section) if cfg_ini.has_section(section) else []
    return [(key, value) for key, value in options if key not in defaults]


PLUGIN_PREFIX = 'plugin_'
CORE_SECTION_PATTERN = 'tank|core'
CORE_SECTION_OLD = 'tank'
CORE_SECTION_NEW = 'core'


def parse_sections(cfg_ini):
    """
    :type cfg_ini: ConfigParser
    """
    return [Section(section.lower(),
                    guess_plugin(section.lower()),
                    without_defaults(cfg_ini, section))
            for section in cfg_ini.sections()
            if not re.match(CORE_SECTION_PATTERN, section.lower()) and section.lower() not in DEPRECATED_SECTIONS]


class PluginInstance(object):
    def __init__(self, name, package_and_section):
        self.name = name
        self.enabled = len(package_and_section) > 0
        try:
            package_path, self.section_name = package_and_section.split()
            self.package = Package(package_path)
        except ValueError:
            self.package = Package(package_and_section)
            self.section_name = self._guess_section_name()
        self.plugin_name = self.package.plugin_name

    def __repr__(self):
        return self.name

    def _guess_section_name(self):
        package_map = {
            'Aggregator': 'aggregator',
            'Autostop': 'autostop',
            'BatteryHistorian': 'battery_historian',
            'Bfg': 'bfg',
            'Console': 'console',
            'DataUploader': 'meta',
            'JMeter': 'jmeter',
            'JsonReport': 'json_report',
            'Maven': 'maven',
            'Monitoring': 'monitoring',
            'Pandora': 'pandora',
            'Phantom': 'phantom',
            'RCAssert': 'rcassert',
            'ResourceCheck': 'rcheck',
            'ShellExec': 'shellexec',
            'ShootExec': 'shootexec',
            'SvgReport': 'svgreport',
            'Telegraf': 'telegraf',
            'TipsAndTricks': 'tips'
        }
        name_map = {
            'aggregate': 'aggregator',
            'overload': 'overload',
            'jsonreport': 'json_report'
        }
        return name_map.get(self.name, package_map.get(self.package.plugin_name, self.name))


def enable_sections(sections, core_opts):
    """

    :type sections: list of Section
    """
    DEPRECATED_PLUGINS = ['yandextank.plugins.Aggregator', 'Tank/Plugins/Aggregator.py']

    plugin_instances = [PluginInstance(key.split('_')[1], value) for key, value in core_opts if
                        key.startswith(PLUGIN_PREFIX) and value not in DEPRECATED_PLUGINS]
    enabled_instances = {instance.section_name: instance for instance in plugin_instances if instance.enabled}
    disabled_instances = {instance.section_name: instance for instance in plugin_instances if not instance.enabled}

    for section in sections:
        if enabled_instances.pop(section.name, None) is not None:
            section.enabled = True
        elif disabled_instances.pop(section.name, None) is not None:
            section.enabled = False
    # add leftovers
    leftovers = set(enabled_instances.keys()) | set(disabled_instances.keys())
    for plugin_instance in filter(
        lambda lo: lo.section_name in leftovers,
        plugin_instances,
    ):
        sections.append(Section(plugin_instance.section_name, plugin_instance.plugin_name, [], plugin_instance.enabled))
    return sections


def combine_sections(sections):
    """
    :type sections: list of Section
    :rtype: list of Section
    """
    PLUGINS_TO_COMBINE = {
        'Phantom': ('phantom', 'multi', True),
        'Bfg': ('bfg', 'gun_config', False)
    }
    plugins = {}
    ready_sections = []
    for section in sections:
        if section.plugin in PLUGINS_TO_COMBINE:
            try:
                plugins[section.plugin].append(section)
            except KeyError:
                plugins[section.plugin] = [section]
        else:
            ready_sections.append(section)

    for plugin_name, _sections in plugins.items():
        if isinstance(_sections, list):
            parent_name, child_name, is_list = PLUGINS_TO_COMBINE[plugin_name]
            ready_sections.append(Section.from_multiple(_sections, parent_name, child_name, is_list))
    return ready_sections


def core_options(cfg_ini):
    return cfg_ini.items(CORE_SECTION_OLD) if cfg_ini.has_section(CORE_SECTION_OLD) else []


def convert_ini(ini_file):
    cfg_ini = RawConfigParser(strict=False)
    try:
        if isinstance(ini_file, str):
            cfg_ini.read(ini_file)
        else:
            cfg_ini.read_file(ini_file)
    except ParsingError as e:
        raise ConversionError(e.message)

    ready_sections = enable_sections(combine_sections(parse_sections(cfg_ini)), core_options(cfg_ini))

    plugins_cfg_dict = {section.new_name: section.get_cfg_dict() for section in ready_sections}

    plugins_cfg_dict.update({
        'core': dict([Option('core', key, value, CORE_SCHEMA).as_tuple
                      for key, value in without_defaults(cfg_ini, CORE_SECTION_OLD)
                      if not key.startswith(PLUGIN_PREFIX)])
    })
    logger.info('Converted config:\n{}'.format(yaml.dump(plugins_cfg_dict)))
    return plugins_cfg_dict


def convert_single_option(key, value):
    """

    :type value: str
    :type key: str
    :rtype: {str: obj}
    """
    section_name, option_name = key.strip().split('.', 1)
    if not re.match(CORE_SECTION_PATTERN, section_name):
        section = Section(section_name,
                          guess_plugin(section_name),
                          [(option_name, value)])
        return {section.new_name: section.get_cfg_dict()}
    else:
        if option_name.startswith(PLUGIN_PREFIX):
            return {section.new_name: section.get_cfg_dict() for section in enable_sections([], [(option_name, value)])}
        else:
            return {'core': Option('core', option_name, value, CORE_SCHEMA).converted}
