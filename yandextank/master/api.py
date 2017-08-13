import yaml

from yandextank.core.consoleworker import load_core_base_cfg, load_local_base_cfgs
from yandextank.validator.validator import TankConfig


def validate_config(config):
    cfg = yaml.load(config)
    config.close()
    return TankConfig([load_core_base_cfg()] +
                      load_local_base_cfgs() +
                      [cfg]).errors()