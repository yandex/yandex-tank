import logging
import subprocess
import time
import urllib
import sys
import glob
import os
from multiprocessing import Process
from signal import SIGKILL

try:
    from volta.core.core import Core as VoltaCore
    #from volta.analysis import grab, uploader
except Exception:
    raise RuntimeError("Please install volta. https://github.com/yandex-load/volta")

from pkg_resources import resource_filename
from ...common.interfaces import AbstractPlugin, GeneratorPlugin
from .reader import AndroidReader, AndroidStatsReader

logger = logging.getLogger(__name__)


class Plugin(AbstractPlugin, GeneratorPlugin):
    SECTION = "android"
    SECTION_META = "meta"

    def __init__(self, core, cfg, cfg_updater):
        super(Plugin, self).__init__(core, cfg, cfg_updater)
        self.apk_path = None
        self.test_path = None
        self.package = None
        self.package_test = None
        self.clazz = None
        self.device = None
        self.test_runner = None
        self.voltaCore = VoltaCore(cfg)


    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        opts = ["volta_options" ]
        return opts

    def configure(self):
        self.voltaCore.configure()

    def prepare_test(self):
        aggregator = self.core.job.aggregator_plugin

        if aggregator:
            aggregator.reader = AndroidReader()
            aggregator.stats_reader = AndroidStatsReader()


    def start_test(self):
        if self.device:
            logger.info("Start test...")
            self.voltaCore.start_test()

        #TODO добавить артефакты из voltaCore


    def is_test_finished(self):
        #TODO ожидание окончание теста в телефоне


    def end_test(self, retcode):
        self.voltaCore.end_test()
        return retcode

    def get_info(self):
        return AndroidInfo()

    def post_process(self, retcode):
        self.voltaCore.post_process()

class AndroidInfo(object):
    def __init__(self):
        self.address = ''
        self.port = 80
        self.ammo_file = ''
        self.duration = 0
        self.loop_count = 1
        self.instances = 1
        self.rps_schedule = ''
