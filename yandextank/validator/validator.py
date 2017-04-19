import collections
import os
import pkgutil

import yaml
from cerberus import Validator


class ValidationError(Exception):
    pass

BASE_SCHEMA = {
    'core': {
        'type': 'dict'
    },
    'version': {
        'type': 'string'
    }
}
PLUGIN_SCHEMA = {
    'type': 'dict',
    'allow_unknown': True,
    'schema': {
        'package': {'type': 'string', 'empty': False, 'required': True},
        'enabled': {'type': 'boolean'},
    }
}
DEFAULT_SCHEMA_PATH = 'schema.yaml'


def validate_core(config):
    v = Validator(BASE_SCHEMA, allow_unknown=PLUGIN_SCHEMA)
    result = v.validate(config, BASE_SCHEMA)
    if not result:
        raise ValidationError(v.errors)
    return v.normalized(config)


def validate_plugin(config, schema):
    v = Validator(schema, allow_unknown=True)
    if not v.validate(config):
        raise ValidationError(v.errors)
    return v.normalized(config)


def recursive_update(d, u):
    for k, v in u.iteritems():
        if isinstance(v, collections.Mapping):
            r = recursive_update(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d


def load_multiple(*configs):
    l = len(configs)
    if l == 0:
        return {}
    elif l == 1:
        return configs[0]
    elif l == 2:
        return recursive_update(configs[0], configs[1])
    else:
        return load_multiple(recursive_update(configs[0], configs[1]), *configs[2:])


def parse_enabled_plugins(config):
    """
    :returns: [(plugin_name, plugin_package, plugin_config), ...]
    :rtype: list of tuple
    """
    return [(plugin_name, plugin['package'], plugin)
            for plugin_name, plugin in config.items()
            if (plugin_name not in BASE_SCHEMA.keys()) and plugin['enabled']]


def load_schema(filname):
    with open(filname) as f:
        return yaml.load(f)


def validate_plugins(plugins):
    # plugins: [(plugin_name, plugin_package, plugin_config), ...]
    errors = {}
    results = {}
    for plugin_name, package, config in plugins:
        try:
            results[plugin_name] = \
                validate_plugin(config, load_schema(os.path.join(pkgutil.get_loader(package).filename, DEFAULT_SCHEMA_PATH)))
        except ValidationError as e:
            errors[plugin_name] = e.message
    if len(errors) > 0:
        raise ValidationError(dict(errors))
    return results


def validate_all(config):
    core_result = validate_core(config)
    plugins_results = validate_plugins(parse_enabled_plugins(core_result))
    for plugin_name, plugin_conf in plugins_results.items():
        core_result[plugin_name] = plugin_conf
    return core_result
