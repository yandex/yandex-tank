import logging

from ..DataUploader import Plugin as DataUploaderPlugin
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
        self.stats_reader = None
        self.reader = None
        self.core = core
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

    def get_reader(self):
        if self.reader is None:
            self.reader = AndroidReader()
        return self.reader

    def get_stats_reader(self):
        if self.stats_reader is None:
            self.stats_reader = AndroidStatsReader()
        return self.stats_reader

    def prepare_test(self):
        self.core.add_artifact_file(self.volta_core.currents_fname)
        [self.core.add_artifact_file(fname) for fname in self.volta_core.event_fnames.values()]

    def start_test(self):
        self.volta_core.start_test()

    def is_test_finished(self):
        try:
            if hasattr(self.volta_core, 'phone'):
                if hasattr(self.volta_core.phone, 'test_performer'):
                    if not self.volta_core.phone.test_performer._finished:
                        logger.debug('Waiting for phone test for finish...')
                        return -1
                    else:
                        return self.volta_core.phone.test_performer.retcode
        except:
            raise RuntimeError('Unknown exception of android plugin')

    def end_test(self, retcode):
        self.volta_core.end_test()
        uploaders = self.core.get_plugins_of_type(DataUploaderPlugin)
        for uploader in uploaders:
            response = uploader.lp_job.link_mobile_job(
                lp_key=uploader.lp_job.number,
                mobile_key=self.volta_core.uploader.jobno
            )
            logger.info(
                'Linked mobile job %s to %s for plugin: %s. Response: %s',
                self.volta_core.uploader.jobno, uploader.lp_job.number, uploader.backend_type, response
            )
        return retcode

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
