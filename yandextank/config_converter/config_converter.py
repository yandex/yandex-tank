import ConfigParser
import re


def old_plugin_mapper(package):
    MAP = {'Overload': 'DataUploader'}
    return MAP.get(package, package)


def parse_package_name(package_path):
    if package_path.startswith("Tank/Plugins/"):
        package = package_path.split('/')[-1].split('.')[0]
    else:
        package = package_path.split('.')[-1]
    return old_plugin_mapper(package)


SECTIONS_PATTERNS = {
    'Phantom': 'phantom(-.*)?',
    'Aggregator': 'aggregator',
    'Autostop': 'autostop',
    'DataUploader': 'meta|overload',
    'Telegraf': 'telegraf',
    'Monitoring': 'monitoring'
}


class UnrecognizedSection(Exception):
    pass


def guess_plugin(section, core_options):
    for plugin, section_name_pattern in SECTIONS_PATTERNS.items():
        if re.match(section_name_pattern, section):
            return plugin
    else:
        raise UnrecognizedSection('Section {} did not match any plugin'.format(section))


def convert_rps_schedule(value):
    return 'load_profile', {
        'load_type': 'rps',
        'schedule': value
    }


def convert_instances_schedule(value):
    return 'load_profile', {
        'load_type': 'instances',
        'schedule': value
    }


OPTIONS_MAP = {
    'core': {
        'ignore_locks': lambda value: ('ignore_locks', int(value)),
    },
    'Phantom': {
        'rps_schedule': convert_rps_schedule,
        'instances_schedule': convert_instances_schedule,
        'force_stepping': lambda value: ('force_stepping', int(value)),
        'file_cache': lambda value: ('file_cache', int(value)),
        'ammo_limit': lambda value: ('ammo_limit', int(value)),
        'instances': lambda value: ('instances', int(value)),
        'threads': lambda value: ('threads', int(value)),
        'use_caching': lambda value: ('use_caching', bool(int(value))),
        'enum_ammo': lambda value: ('enum_ammo', bool(int(value))),
        'loop': lambda value: ('loop', int(value)),
        'connection_test': lambda value: ('connection_test', bool(int(value)))
    },
    'Aggregator': {
        'precise_cumulative': lambda value: ('precise_cumulative', int(value))
    },
    'DataUploader': {
        'ignore_target_lock': lambda value: ('ignore_target_lock', bool(int(value)))
    }
}


def options_converter(plugin, option):
    key, value = option
    return OPTIONS_MAP.get(plugin, {}).get(key, lambda v: (key, v))(value)


class Section(object):
    def __init__(self, name, plugin, options, enabled=False):
        self.name = name
        self.plugin = plugin
        self.options = [options_converter(plugin, option) for option in options]
        self.enabled = None

    def get_cfg_dict(self, with_meta=True):
        options_dict = dict(self.options)
        if with_meta:
            options_dict.update({'package': 'yandextank.plugins.{}'.format(self.plugin)})
            if self.enabled is not None:
                options_dict.update({'enabled': self.enabled})
        return options_dict

    @classmethod
    def from_multiple(cls, sections, master_name=None):
        """
        :type master_name: str
        :type sections: list of Section
        """
        if len(sections) == 1:
            return sections[0]
        if master_name:
            master_section = filter(lambda section: section.name == master_name, sections)[0]
            rest = filter(lambda section: section.name != master_name, sections)
        else:
            master_section = sections[0]
            master_name = master_section.name
            rest = sections[1:]
        multi_option = ('multi', [section.get_cfg_dict(with_meta=False) for section in rest])
        master_section.options.append(multi_option)
        return Section(master_name, master_section.plugin, master_section.options)


def without_defaults(cfg_ini, section):
    """

    :type cfg_ini: ConfigParser.ConfigParser
    """
    defaults = cfg_ini.defaults()
    options = cfg_ini.items(section) if cfg_ini.has_section(section) else []
    return [(key, value) for key, value in options if key not in defaults.keys()]


PLUGIN_PREFIX = 'plugin_'
CORE_SECTION = 'tank'


def parse_sections(cfg_ini, core_options):
    """

    :type cfg_ini: ConfigParser.ConfigParser
    """
    return [Section(section,
                    guess_plugin(section, dict(core_options)),
                    without_defaults(cfg_ini, section))
            for section in cfg_ini.sections()
            if section != CORE_SECTION]


def enable_sections(sections, core_options):
    """

    :type sections: list of Section
    """
    enabled_plugins = [parse_package_name(value) for key, value in core_options if
                       key.startswith(PLUGIN_PREFIX) and value]
    disabled_plugins = [parse_package_name(value) for key, value in core_options if
                        key.startswith(PLUGIN_PREFIX) and not value]
    for section in sections:
        if section.plugin in enabled_plugins:
            section.enabled = True
            enabled_plugins.remove(section.plugin)
        if section.plugin in disabled_plugins:
            section.enabled = False
    for plugin in enabled_plugins:
        sections.append(Section(plugin.lower(), plugin, [], True))
    return sections


def partition(l, predicate):
    return reduce(lambda x, y: (x[0] + [y], x[1]) if predicate(y) else (x[0], x[1] + [y]), l, ([], []))


def combine_sections(sections):
    """

    :type sections: list of Section
    """
    PLUGINS_TO_COMBINE = {
        'Phantom': 'phantom'
    }
    plugins = {}
    for section in sections:
        if section.plugin in PLUGINS_TO_COMBINE.keys():
            try:
                plugins[section.plugin].append(section)
            except KeyError:
                plugins[section.plugin] = [section]
        else:
            plugins[section.plugin] = section

    for plugin_name, _sections in plugins.items():
        if isinstance(_sections, list):
            plugins[plugin_name] = Section.from_multiple(_sections, PLUGINS_TO_COMBINE[plugin_name])

    return plugins.values()


def convert_ini(ini_file):
    cfg_ini = ConfigParser.ConfigParser()
    cfg_ini.read(ini_file)
    core_options = cfg_ini.items(CORE_SECTION) if cfg_ini.has_section(CORE_SECTION) else []
    ready_sections = enable_sections(combine_sections(parse_sections(cfg_ini, core_options)), core_options)

    plugins_cfg_dict = {section.name: section.get_cfg_dict() for section in ready_sections}

    plugins_cfg_dict.update({
        'core': dict([options_converter('core', option) for option in without_defaults(cfg_ini, CORE_SECTION)
                      if not option[0].startswith(PLUGIN_PREFIX)])
    })
    return plugins_cfg_dict
