"""
Run maven test as load test
"""
from __future__ import division, absolute_import

import logging
import subprocess
import time

from builtins import super
from ...common.resource import manager as resource_manager
from ...common.interfaces import AbstractPlugin, GeneratorPlugin

from .console import MavenInfoWidget
from .reader import MavenReader, MavenStatsReader
from ..Console import Plugin as ConsolePlugin

logger = logging.getLogger(__name__)


class Plugin(AbstractPlugin, GeneratorPlugin):

    SECTION = "maven"

    def __init__(self, core):
        # FIXME python version 2.7 does not support this syntax. super() should
        # have arguments in Python 2
        super().__init__(core)
        self.maven_cmd = "mvn"
        self.process = None
        self.process_stderr = None
        self.process_start_time = None

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        opts = ["pom", "testcase", "mvn_args"]
        return opts

    def configure(self):
        # plugin part
        self.pom = resource_manager.resource_filename(
            self.get_option("pom", "pom.xml"))
        self.testcase = self.get_option("testcase", "")
        self.maven_args = self.get_option("mvn_args", '').split()

    def prepare_test(self):
        aggregator = self.core.job.aggregator_plugin

        if aggregator:
            aggregator.reader = MavenReader()
            aggregator.stats_reader = MavenStatsReader()

        try:
            console = self.core.get_plugin_of_type(ConsolePlugin)
        except KeyError as ex:
            logger.debug("Console not found: %s", ex)
            console = None

        if console:
            widget = MavenInfoWidget(self)
            console.add_info_widget(widget)
            if aggregator:
                aggregator.add_result_listener(widget)

    def start_test(self):
        args = [self.maven_cmd, "test", "-Dtest=%s" % self.testcase
                ] + self.maven_args + ["-f", self.pom]
        logger.info("Starting: %s", args)
        self.process_start_time = time.time()
        process_stderr_file = self.core.mkstemp(".log", "maven_")
        self.core.add_artifact_file(process_stderr_file)
        self.process_stderr = open(process_stderr_file, 'w')
        self.process = subprocess.Popen(
            args,
            stderr=self.process_stderr,
            stdout=self.process_stderr,
            close_fds=True)

    def is_test_finished(self):
        retcode = self.process.poll()
        if retcode is not None:
            logger.info("Subprocess done its work with exit code: %s", retcode)
            return abs(retcode)
        else:
            return -1

    def end_test(self, retcode):
        if self.process and self.process.poll() is None:
            logger.warn(
                "Terminating worker process with PID %s", self.process.pid)
            self.process.terminate()
            if self.process_stderr:
                self.process_stderr.close()
        else:
            logger.debug("Seems subprocess finished OK")
        return retcode
