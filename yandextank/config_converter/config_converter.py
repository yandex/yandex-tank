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


def get_plugin_sections(package_name):
    pass


SECTIONS_PATTERNS = {
    'Phantom': 'phantom(-.*)?',
    'Aggregator': 'aggregator',
    'Autostop': 'autostop',
    'Monitoring': 'monitoring',
    'DataUploader': 'meta|overload',
    'Telegraf': 'monitoring|telegraf'
}


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
        'loop': lambda value: ('loop', int(value))
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


class PluginInstance(object):
    def __init__(self, plugin, options):
        self.options = [options_converter(plugin, option) for option in options]

    def get_cfg_dict(self, package_name, include_meta=True):
        options_dict = dict(self.options)
        if include_meta:
            options_dict.update({
                'package': 'yandextank.plugins.%s' % package_name,
                'enabled': True
            })
        return options_dict


class Plugin(object):
    def __init__(self, package_and_section, cfg_ini):
        try:
            package_path, section = package_and_section.split()
            self.package_name = parse_package_name(package_path)
            self.instances = {section: PluginInstance(self.package_name, cfg_ini.options(section))}
        except ValueError:
            self.package_name = parse_package_name(package_and_section)
            sections = [section for section in cfg_ini.sections()
                        if re.match(SECTIONS_PATTERNS[self.package_name], section)]
            self.instances = {section: PluginInstance(self.package_name, cfg_ini.items(section)) for section in
                              sections}

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


def parse_plugins(core_options, cfg_ini):
    CORE_OPTIONS = ['artifacts_base_dir', 'ignore_locks', 'lock_dir']
    return [Plugin(package_and_section, cfg_ini) for alias, package_and_section in core_options
            if alias.startswith(PLUGIN_PREFIX) and package_and_section]


def convert_ini(ini_file):
    CORE_SECTION = 'tank'
    cfg_ini = ConfigParser.ConfigParser()
    cfg_ini.read(ini_file)
    core_options = cfg_ini.items(CORE_SECTION)
    enabled_plugins = parse_plugins(core_options, cfg_ini)
    plugins_cfg_dict = dict(reduce(lambda a, b: a + b, [plugin.get_cfg_tuple() for plugin in enabled_plugins]))
    plugins_cfg_dict.update({
        'core': dict([options_converter('core', option) for option in core_options
                      if not option[0].startswith(PLUGIN_PREFIX)])
    })
    return plugins_cfg_dict
