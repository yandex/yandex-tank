import logging

from ..DataUploader import Plugin as DataUploaderPlugin
from .reader import AndroidReader, AndroidStatsReader
from ...common.interfaces import AbstractPlugin

try:
    from volta.core.core import Core as VoltaCore
except Exception:
    raise RuntimeError("Please install volta. https://github.com/yandex-load/volta")

logger = logging.getLogger(__name__)


class Plugin(AbstractPlugin):
    SECTION = "android"
    SECTION_META = "meta"

    def __init__(self, core, cfg, name):
        self.stats_reader = None
        self.reader = None
        super(Plugin, self).__init__(core, cfg, name)
        self.device = None
        try:
            self.cfg = cfg['volta_options']
            for key, value in self.cfg.items():
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
        try:
            self.volta_core.start_test()
        # FIXME raise/catch appropriate exception here
        except:  # noqa: E722
            logger.info('Failed to start test of Android plugin', exc_info=True)
            return 1

    def is_test_finished(self):
        try:
            if hasattr(self.volta_core, 'phone'):
                if hasattr(self.volta_core.phone, 'test_performer'):
                    if not self.volta_core.phone.test_performer:
                        logger.warning('There is no test performer process on the phone, interrupting test')
                        return 1
                    if not self.volta_core.phone.test_performer.is_finished():
                        logger.debug('Waiting for phone test to finish...')
                        return -1
                    else:
                        return self.volta_core.phone.test_performer.retcode
        # FIXME raise/catch appropriate exception here
        except:  # noqa: E722
            logger.error('Unknown exception of Android plugin. Interrupting test', exc_info=True)
            return 1

    def end_test(self, retcode):
        try:
            self.volta_core.end_test()
            uploaders = self.core.get_plugins_of_type(DataUploaderPlugin)
            for uploader in uploaders:
                response = uploader.lp_job.api_client.link_mobile_job(
                    lp_key=uploader.lp_job.number,
                    mobile_key=self.volta_core.uploader.jobno
                )
                logger.info(
                    'Linked mobile job %s to %s for plugin: %s. Response: %s',
                    self.volta_core.uploader.jobno, uploader.lp_job.number, uploader.backend_type, response
                )
        # FIXME raise/catch appropriate exception here
        except:  # noqa: E722
            logger.error('Failed to complete end_test of Android plugin', exc_info=True)
            retcode = 1
        return retcode

    def get_info(self):
        return AndroidInfo()

    def post_process(self, retcode):
        try:
            self.volta_core.post_process()
        # FIXME raise/catch appropriate exception here
        except:  # noqa: E722
            logger.error('Failed to complete post_process of Android plugin', exc_info=True)
            retcode = 1
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
