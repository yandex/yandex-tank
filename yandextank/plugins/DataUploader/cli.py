import ConfigParser
import argparse
import glob
import json
import logging
import os
import socket

import sys

import pwd
from StringIO import StringIO
from urlparse import urljoin

from datetime import datetime
import pkg_resources

from .client import APIClient
from .plugin import LPJob

CONFIG_FILE = 'saved_conf.yaml'
DATA_LOG = 'test_data.log'
MONITORING_LOG = 'monitoring.log'
SECTION = 'meta'

logger = logging.getLogger('')
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
handler.setLevel(logging.INFO)
logger.addHandler(handler)
verbose_handler = logging.FileHandler(
    datetime.now().strftime("post_loader_%Y-%m-%d_%H-%M-%S.log"), 'w')
verbose_handler.setLevel(logging.DEBUG)
logger.addHandler(verbose_handler)


def read_config(shooting_dir):
    config_file = glob.glob(os.path.join(shooting_dir, CONFIG_FILE))[0]
    logger.info('Config file found: %s' % config_file)
    config = ConfigParser.ConfigParser()
    config.read(config_file)
    return config


def get_lp_config(config):
    """
    looks for config file in shooting_dir,
    returns config dict of section 'meta'
    :rtype: dict
    """
    lp_config = dict(config.items(SECTION))
    for key in sorted(lp_config.keys()):
        logger.debug('%s: %s' % (key, lp_config[key]))
    return lp_config


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
        for line in f:
            lp_job.push_monitoring_data(line.strip())
            sys.stdout.write('.')
            sys.stdout.flush()
    sys.stdout.write('\n')


def send_config_snapshot(config, lp_job):
    config.set(SECTION, 'launched_from', 'post-loader')
    output = StringIO()
    config.write(output)
    lp_job.send_config_snapshot(output.getvalue())


def edit_metainfo(lp_config, lp_job):
    lp_job.edit_metainfo(is_regression=lp_config.get('regress'),
                         regression_component=lp_config.get('component'),
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
    os.symlink(os.path.relpath(shooting_dir, plugin_dir), link_name)
    logger.info('Symlink created: {}'.format(os.path.abspath(link_name)))


def post_loader():
    parser = argparse.ArgumentParser()
    parser.add_argument('shooting_dir',
                        help='Directory containing shooting artifacts')
    shooting_dir = parser.parse_args().shooting_dir
    assert os.path.exists(shooting_dir), 'Directory not found'

    config = read_config(shooting_dir)
    lp_config = get_lp_config(config)

    api_client = APIClient(base_url=lp_config['api_address'],
                           user_agent='Lunapark/{}'.format(pkg_resources.require('yatank-internal-lunapark')[0].version)
                           # todo: add timeouts
                           )
    lp_job = LPJob(
        client=api_client,
        target_host=lp_config.get('target_host'),
        target_port=lp_config.get('target_port'),
        person=lp_config.get(
            'operator',
            '') or pwd.getpwuid(
            os.geteuid())[0],
        task=lp_config['task'],
        name=lp_config['job_name'],
        description=lp_config['job_dsc'],
        tank=socket.getfqdn())
    edit_metainfo(lp_config, lp_job)
    upload_data(shooting_dir, DATA_LOG, lp_job)
    send_config_snapshot(config, lp_job)
    try:
        upload_monitoring(shooting_dir, MONITORING_LOG, lp_job)
    except AssertionError as e:
        logger.error(e)
    lp_job.close(0)
    make_symlink(shooting_dir, lp_job.number)
    logger.info(
        'LP job created: {}'.format(
            urljoin(
                api_client.base_url, str(
                    lp_job.number))))


if __name__ == '__main__':
    post_loader()
