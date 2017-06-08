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
    'Monitoring': 'monitoring',
    'DataUploader': 'meta|overload',
    'Telegraf': 'monitoring|telegraf'
}


class UnrecognizedSection(Exception):
    pass


def guess_plugin(section):
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
    def __init__(self, name, plugin, options):
        self.name = name
        self.plugin = plugin
        self.options = [options_converter(plugin, option) for option in options]

    def get_cfg_dict(self):
        options_dict = dict(self.options)
        return options_dict

    @classmethod
    def from_multiple(cls, sections, master_name=None):
        """
        :type master_name: str
        :type sections: list of Section
        """
        if master_name:
            master_section = filter(lambda section: section.name == master_name, sections)[0]
            rest = filter(lambda section: section.name != master_name, sections)
        else:
            master_section = sections[0]
            master_name = master_section.name
            rest = sections[1:]
        multi_option = ('multi', [section.get_cfg_dict() for section in rest])
        options = master_section.options.append(multi_option)
        return Section(master_name, master_section.plugin, options)


def to_plugins(instances):
    """

    :type instances: list of Section
    """
    plugins_instances = {}
    for instance in instances:
        try:
            plugins_instances[instance.plugin].append(instance)
        except KeyError:
            plugins_instances[instance.plugin] = [instance]
    return {plugin: Plugin(instances) for plugin, instances in plugins_instances.items()}


def without_defaults(cfg_ini, section):
    """

    :type cfg_ini: ConfigParser.ConfigParser
    """
    defaults = cfg_ini.defaults()
    return [(key, value) for key, value in cfg_ini.items(section) if key not in defaults.keys()]


class Plugin(object):
    def __init__(self, instances):
        self.instances = instances
        self.package_name = instances[0].plugin
        self.enabled = False
        # try:
        #     package_path, section = package_and_section.split()
        #     self.package_name = parse_package_name(package_path)
        #     self.instances = {section: PluginInstance(self.package_name, without_defaults(cfg_ini, section))}
        # except ValueError:
        #     self.package_name = parse_package_name(package_and_section)
        #     sections = [section for section in cfg_ini.sections()
        #                 if re.match(SECTIONS_PATTERNS[self.package_name], section)]
        #     self.instances = {section: PluginInstance(self.package_name, without_defaults(cfg_ini, section)) for section in
        #                       sections}

    def get_cfg_tuple(self):
        if self.package_name == 'Phantom' and len(self.instances) > 1:
            master_cfg = self.instances['phantom'].get_cfg_dict(self.package_name)
            multi = [instance.get_cfg_dict(self.package_name, False) for section_name, instance in self.instances.items()
                     if section_name != 'phantom']
            master_cfg['multi'] = multi
            return [('phantom', master_cfg)]
        else:
            return [(section_name, instance.get_cfg_dict(self.package_name)) for section_name, instance
                    in self.instances.items()]


PLUGIN_PREFIX = 'plugin_'
CORE_SECTION = 'tank'


def parse_sections(cfg_ini):
    return [Section(section, guess_plugin(section), cfg_ini.items(section)) for section in cfg_ini.sections()
            if section != CORE_SECTION]


def enable_plugins(plugins, core_options):
    pass


def partition(l, predicate):
    return reduce(lambda x, y: (x[0]+[y], x[1]) if predicate(y) else (x[0], x[1]+[y]), l,  ([], []))


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
    core_options = cfg_ini.items(CORE_SECTION)
    enabled_plugins = enable_plugins(combine_sections(parse_sections(cfg_ini)), core_options)

    plugins_cfg_dict = dict(reduce(lambda a, b: a + b, [plugin.get_cfg_tuple() for plugin in enabled_plugins]))
    plugins_cfg_dict.update({
        'core': dict([options_converter('core', option) for option in without_defaults(cfg_ini, CORE_SECTION)
                      if not option[0].startswith(PLUGIN_PREFIX)])
    })
    return plugins_cfg_dict
