import yaml
from StringIO import StringIO

from yandextank.config_converter.converter import ConversionError
from yandextank.core.consoleworker import load_core_base_cfg, load_local_base_cfgs, convert_ini
from yandextank.validator.validator import TankConfig


def validate_config(config, fmt):
    def response(cfg, errors):
        return {'config': cfg, 'errors': errors}

    if fmt == 'ini':
        stream = StringIO(str(config.read()))
        try:
            cfg = convert_ini(stream)
        except ConversionError as e:
            return response({}, [e.message])
    else:
        cfg = yaml.load(config)
    config.close()
    tank_config = TankConfig([load_core_base_cfg()] +
                             load_local_base_cfgs() +
                             [cfg])
    return response(tank_config.raw_config_dict, tank_config.errors())
