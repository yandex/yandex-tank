import io
import yaml

from yandextank.core.consoleworker import load_core_base_cfg, load_local_base_cfgs, load_cfg, convert_ini
from yandextank.validator.validator import TankConfig


def validate_config(config, fmt):
    if fmt == 'ini':
        stream = io.StringIO(str(config.read(), 'utf-8'))
        cfg = convert_ini(stream)
    else:
        cfg = yaml.load(config)
    config.close()
    tank_config = TankConfig([load_core_base_cfg()] +
                      load_local_base_cfgs() +
                      [cfg])
    return {
        'config': tank_config.raw_config_dict,
        'errors': tank_config.errors()
    }