import logging
import time

import requests
from yandextank.plugins.Overload.client import OverloadClient

from .reader import AndroidReader, AndroidStatsReader
from ...common.interfaces import AbstractPlugin, GeneratorPlugin

try:
    from volta.core.core import Core as VoltaCore
except Exception:
    raise RuntimeError("Please install volta. https://github.com/yandex-load/volta")

logger = logging.getLogger(__name__)


class Plugin(AbstractPlugin, GeneratorPlugin):
    SECTION = "android"
    SECTION_META = "meta"

    def __init__(self, core, cfg, cfg_updater):
        try:
            super(Plugin, self).__init__(core, cfg, cfg_updater)
            self.device = None
            self.cfg = cfg['volta_options']
            for key, value in self.cfg.iteritems():
                if not isinstance(value, dict):
                    logger.debug('Malformed VoltaConfig key: %s value %s', key, value)
                    raise RuntimeError('Malformed VoltaConfig passed, key: %s. Should by dict' % key)
        except AttributeError:
            logger.error('Failed to read Volta config', exc_info=True)
        self.volta_core = VoltaCore(self.cfg)

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        opts = ["volta_options"]
        return opts

    def configure(self):
        self.volta_core.configure()

    def prepare_test(self):
        aggregator = self.core.job.aggregator_plugin
        if aggregator:
            aggregator.reader = AndroidReader()
            aggregator.stats_reader = AndroidStatsReader()
        self.core.add_artifact_file(self.volta_core.currents_fname)
        [self.core.add_artifact_file(fname) for fname in self.volta_core.event_fnames.values()]

    def start_test(self):
        self.volta_core.start_test()

    def is_test_finished(self):
        if hasattr(self.volta_core, 'phone'):
            if hasattr(self.volta_core.phone, 'test_performer'):
                if not self.volta_core.phone.test_performer._finished:
                    logger.debug('Waiting for phone test for finish...')
                    return -1
                else:
                    return self.volta_core.phone.test_performer.retcode

    def end_test(self, retcode):
        self.volta_core.end_test()

        mobile_key = self.volta_core.uploader.jobno
        logger.info("Mobile jobno: %s", mobile_key)

        jobno = self.core.status['uploader']['job_no']
        logger.info("Simple jobno: %s", jobno)

        web_link = self.core.status['uploader']['web_link']
        url = web_link.replace(str(jobno), '')
        logger.info("Url: %s", url)

        self.link_jobs(url, jobno, mobile_key)
        return retcode

    def link_jobs(self, url, jobno, mobile_key):
        api_client = OverloadClient()
        api_client.set_api_address(url)
        api_client.session.verify = False

        addr = "/api/job/{jobno}/edit.json".format(jobno=jobno)
        data = {
            'mobile_key': mobile_key
        }

        logger.info("Jobs link request: url = %s, data = %s", url + addr, data)
        while True:
            try:
                response = api_client.post(addr, data)
                return response
            except requests.exceptions.HTTPError as ex:
                logger.debug("Got error for jobs link request: %s", ex)
                if ex.response.status_code == 423:
                    logger.warn(
                        "Overload is under maintenance, will retry in 5s...")
                    time.sleep(5)
                else:
                    raise ex

    def get_info(self):
        return AndroidInfo()

    def post_process(self, retcode):
        self.volta_core.post_process()
        return retcode


class AndroidInfo(object):
    def __init__(self):
        self.address = ''
        self.port = 80
        self.ammo_file = ''
        self.duration = 0
        self.loop_count = 1
        self.instances = 1
        self.rps_schedule = ''
