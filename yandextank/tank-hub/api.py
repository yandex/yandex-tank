import yaml
from StringIO import StringIO

from werkzeug.exceptions import BadRequest

from yandextank.config_converter.converter import ConversionError
from yandextank.core.consoleworker import load_core_base_cfg, load_local_base_cfgs, convert_ini
from yandextank.validator.validator import TankConfig


def log_exception(e):

    """

    :param e: Exception info
    :type e: Exception
    """
    pass


def validate_config(config, fmt):
    def response(full_cfg, errors):
        return {'config': full_cfg, 'errors': errors}

    if fmt == 'ini':
        stream = StringIO(str(config.read()))
        config.close()
        try:
            cfg = convert_ini(stream)
            tank_config = TankConfig([load_core_base_cfg()] +
                                     load_local_base_cfgs() +
                                     [cfg])
            return response(tank_config.raw_config_dict, tank_config.errors())
        except ConversionError as e:
            return response({}, [e.message])
        except Exception as e:
            log_exception(e)
            raise BadRequest()
    else:
        try:
            cfg = yaml.load(config)
            config.close()
            tank_config = TankConfig([load_core_base_cfg()] +
                                     load_local_base_cfgs() +
                                     [cfg])
            return response(tank_config.raw_config_dict, tank_config.errors())
        except Exception as e:
            log_exception(e)
            return BadRequest


def choose_tank(location, requirements):
    return
