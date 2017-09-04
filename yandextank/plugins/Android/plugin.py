import logging
from ...common.interfaces import AbstractPlugin, GeneratorPlugin
from .reader import AndroidReader, AndroidStatsReader
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
