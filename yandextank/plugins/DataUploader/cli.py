import argparse
import glob
import json
import logging
import os
import socket

import sys

import pwd
import threading
from urllib.parse import urljoin

from datetime import datetime
import pkg_resources
import yaml
from cerberus import Validator

from yandextank.core import TankCore
from yandextank.core.tankcore import VALIDATED_CONF
from yandextank.validator.validator import ValidationError, load_yaml_schema
from .client import APIClient, OverloadClient, LPRequisites
from .plugin import LPJob, BackendTypes
from .plugin import Plugin as DataUploader

DATA_LOG = 'test_data.log'
MONITORING_LOG = 'monitoring.log'
SECTION = 'meta'


def get_logger():
    global logger
    logger = logging.getLogger('')
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)
    verbose_handler = logging.FileHandler(
        datetime.now().strftime("post_loader_%Y-%m-%d_%H-%M-%S.log"), 'w')
    verbose_handler.setLevel(logging.DEBUG)
    logger.addHandler(verbose_handler)


def from_tank_config(test_dir):
    try:
        config_file = glob.glob(os.path.join(test_dir, VALIDATED_CONF))[0]
        logger.info('Config file found: %s' % config_file)
    except IndexError:
        raise OSError('Config file {} not found in {}'.format(VALIDATED_CONF, test_dir))

    with open(config_file) as f:
        tank_cfg = yaml.load(f, Loader=yaml.FullLoader)
    try:
        section, config = next(filter(
            lambda item: 'DataUploader' in item[1].get('package', ''),
            tank_cfg.items(),
        ))
    except StopIteration:
        logger.warning('DataUploader configuration not found in {}'.format(config_file))
        section, config = None, {}
    return section, config


def check_log(log_name):
    assert os.path.exists(log_name), \
        'Data log {} not found\n'.format(log_name) + \
        'JsonReport plugin should be enabled when launching Yandex-tank'


def upload_data(shooting_dir, log_name, lp_job):
    data_log = os.path.join(shooting_dir, log_name)
    check_log(data_log)
    sys.stdout.write('Uploading test data')
    with open(data_log, 'r') as f:
        for line in f:
            data = json.loads(line.strip())
            lp_job.push_test_data(data['data'], data['stats'])
            sys.stdout.write('.')
            sys.stdout.flush()
    sys.stdout.write('\n')


def upload_monitoring(shooting_dir, log_name, lp_job):
    data_log = os.path.join(shooting_dir, log_name)
    check_log(data_log)
    sys.stdout.write('Uploading monitoring data')
    with open(data_log, 'r') as f:
        for line in f.readlines():
            lp_job.push_monitoring_data(json.loads(line.strip()))
            sys.stdout.write('.')
            sys.stdout.flush()
    sys.stdout.write('\n')


def send_config_snapshot(config, lp_job):
    lp_job.send_config(LPRequisites.CONFIGINFO, yaml.dump(config))


def edit_metainfo(lp_config, lp_job):
    lp_job.edit_metainfo(regression_component=lp_config.get('component'),
                         cmdline=lp_config.get('cmdline'),
                         ammo_path=lp_config.get('ammo_path'),
                         loop_count=lp_config.get('loop_count'))


def get_plugin_dir(shooting_dir):
    DIRNAME = 'lunapark'
    parent = os.path.abspath(os.path.join(shooting_dir, os.pardir))
    if os.path.basename(parent) == DIRNAME:
        return parent
    else:
        plugin_dir = os.path.join(parent, DIRNAME)
        if not os.path.exists(plugin_dir):
            os.makedirs(plugin_dir)
        return plugin_dir


def make_symlink(shooting_dir, name):
    plugin_dir = get_plugin_dir(shooting_dir)
    link_name = os.path.join(plugin_dir, str(name))
    try:
        os.symlink(os.path.relpath(shooting_dir, plugin_dir), link_name)
    except OSError:
        logger.warning('Unable to create symlink for artifact: %s', link_name)
    else:
        logger.info('Symlink created: {}'.format(os.path.abspath(link_name)))


class ConfigError(Exception):
    pass


def post_loader():
    CONFIG_SCHEMA = load_yaml_schema(pkg_resources.resource_filename('yandextank.plugins.DataUploader',
                                                                     'config/postloader_schema.yaml'))

    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('-c', '--config', help='YAML config. Format:\n{}'.format(yaml.dump(CONFIG_SCHEMA)))
    parser.add_argument('-a', '--api_address',
                        help='service to upload test results to, e.g. https://overload.yandex.net')
    parser.add_argument('-t', '--target', help='Address of the tested target, host[:port]')
    parser.add_argument('-o', '--operator', help='User who conducted the test')
    parser.add_argument('--task', help='task name, for Lunapark users only')
    parser.add_argument('--job_name', help='Job name')
    parser.add_argument('--job_dsc', help='Job description')
    parser.add_argument('--token', help='path to token file, for Overload users only')
    parser.add_argument('test_dir',
                        help='Directory containing test artifacts')
    args = parser.parse_args()
    assert os.path.exists(args.test_dir), 'Directory {} not found'.format(args.test_dir)
    get_logger()
    # load cfg
    if args.config:
        with open(args.config) as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
            section = None
    else:
        section, config = from_tank_config(args.test_dir)
    # parse target host and port
    if args.target is not None:
        try:
            target_host, target_port = args.target.rsplit(':', 1)
        except ValueError:
            target_host, target_port = args.target, None
    else:
        target_host, target_port = None, None
    # update cfg from cli options
    for key, value in [('api_address', args.api_address),
                       ('target_host', target_host),
                       ('target_port', target_port),
                       ('operator', args.operator),
                       ('task', args.task),
                       ('job_name', args.job_name),
                       ('job_dsc', args.job_dsc),
                       ('token_file', args.token)]:
        if value is not None:
            config[key] = value
    # Validation
    v = Validator(schema=CONFIG_SCHEMA,
                  allow_unknown=True)
    if not v.validate(config):
        raise ValidationError(v.errors)
    config = v.normalized(config)

    # lunapark or overload?
    backend_type = BackendTypes.identify_backend(config['api_address'], section)
    if backend_type == BackendTypes.LUNAPARK:
        client = APIClient
        api_token = None
    elif backend_type == BackendTypes.OVERLOAD:
        client = OverloadClient
        try:
            api_token = DataUploader.read_token(config["token_file"])
        except KeyError:
            raise ConfigError('Token file required')
    else:
        raise RuntimeError("Backend type doesn't match any of the expected")

    user_agent = ' '.join(('Uploader/{}'.format(DataUploader.VERSION),
                           TankCore.get_user_agent()))
    api_client = client(base_url=config['api_address'],
                        user_agent=user_agent,
                        api_token=api_token,
                        core_interrupted=threading.Event()
                        # todo: add timeouts
                        )
    lp_job = LPJob(
        client=api_client,
        target_host=config.get('target_host'),
        target_port=config.get('target_port'),
        person=config.get('operator') or pwd.getpwuid(os.geteuid())[0],
        task=config.get('task'),
        name=config['job_name'],
        description=config['job_dsc'],
        tank=socket.getfqdn())
    edit_metainfo(config, lp_job)
    upload_data(args.test_dir, DATA_LOG, lp_job)
    send_config_snapshot(config, lp_job)
    try:
        upload_monitoring(args.test_dir, MONITORING_LOG, lp_job)
    except AssertionError as e:
        logger.error(e)
    lp_job.close(0)
    make_symlink(args.test_dir, lp_job.number)
    logger.info(
        'LP job created: {}'.format(
            urljoin(
                api_client.base_url, str(
                    lp_job.number))))


if __name__ == '__main__':
    post_loader()
