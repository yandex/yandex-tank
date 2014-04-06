""" Module to perform distributed tests """
# TODO: how to deal with remote monitoring data?
import fnmatch
import os
import random
import time
import traceback

from tankcore import AbstractPlugin
from Tank.API.client import TankAPIClient


class DistributedPlugin(AbstractPlugin):
    SECTION = "distributed"

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        # config options
        self.running_tests = []
        self.tanks_count = 1
        self.configs = []
        self.options = []
        self.files = []
        self.artifacts_to_download = []
        self.chosen_tanks = []
        self.exclusive_mode = 1

        # regular fields
        self.api_clients = []
        self.api_client_class = TankAPIClient
        self.config_file = None

    def get_available_options(self):
        return ["api_port", "api_timeout",
                "tanks_pool", "tanks_count", "random_tanks", "exclusive_mode"
                                                             "configs", "options", "files", "download_artifacts"]

    def configure(self):
        api_timeout = int(self.get_option("api_timeout", 5))
        self.exclusive_mode = int(self.get_option("exclusive_mode", self.exclusive_mode))

        tanks_pool = self.get_multiline_option("tanks_pool")
        count = self.get_option("tanks_count", self.tanks_count)
        if count == 'all':
            self.tanks_count = len(tanks_pool)
        else:
            self.tanks_count = int(count)

        random_tanks = int(self.get_option("random_tanks", 0))
        if random_tanks:
            random.shuffle(tanks_pool)

        self.configs = self.get_multiline_option("configs")
        self.options = self.get_multiline_option("options", self.options)
        self.files = self.get_multiline_option("files", self.files)
        self.artifacts_to_download = self.get_multiline_option("download_artifacts", self.artifacts_to_download)

        # done reading options, do some preparations

        for tank in tanks_pool:
            self.api_clients.append(self.api_client_class(tank, api_timeout))

        self.config_file = self.compose_load_ini(self.configs, self.options)
        self.core.add_artifact_file(self.config_file)

    def prepare_test(self):
        """ choosing tanks, uploading files, calling configure and prepare """
        self.choose_tanks()
        self.prepare_tanks()

    def start_test(self):
        """ starting test  """
        for tank in self.chosen_tanks:
            tank.start_test()
            self.running_tests.append(tank)

    def is_test_finished(self):
        """ polling for the status of remote jobs """
        retcode = AbstractPlugin.is_test_finished(self)
        new_running = []
        for tank in self.running_tests:
            status = tank.get_test_status()
            if status["status"] == TankAPIClient.RUNNING:
                new_running.append(tank)
            else:
                self.log.info("Tank has finished the test: %s", tank.address)

        self.running_tests = new_running

        if not self.running_tests:
            retcode = 0

        return retcode

    def end_test(self, retcode):
        """ call graceful shutdown for all tests """
        self.log.info("Shutting down remote tests...")
        for tank in self.running_tests:
            tank.interrupt()

        for tank in self.chosen_tanks:
            while tank.get_test_status()["status"] != TankAPIClient.FINISHED:
                self.log.info("Waiting for test shutdown on %s...", tank.address)
                time.sleep(5)

    def post_process(self, retcode):
        """ download artifacts """
        if self.artifacts_to_download:
            for tank in self.chosen_tanks:
                self.download_artifacts(tank)

    @staticmethod
    def get_key():
        return __file__

    def compose_load_ini(self, configs, options):
        fname = self.core.mkstemp('.ini', 'load_')
        self.log.debug("Composing config: %s", fname)
        with open(fname, "w") as fd:
            for cfile in configs:
                fd.write("# === %s ===\n" % cfile)
                with open(cfile) as orig:
                    fd.write(orig.read())
                fd.write("\n\n")

            if options:
                fd.write("\n\n#Command-line options added below\n")

                for option_str in options:
                    try:
                        section = option_str[:option_str.index('.')]
                        option = option_str[option_str.index('.') + 1:option_str.index('=')]
                    except ValueError:
                        section = 'DEFAULT'
                        option = option_str[:option_str.index('=')]
                    value = option_str[option_str.index('=') + 1:]
                    self.log.debug("Append option: %s => [%s] %s=%s", option_str, section, option, value)
                    fd.write("[%s]\n%s=%s\n" % (section, option, value))

        return fname

    def choose_tanks(self):
        self.log.info("Choosing %s tanks from pool: %s", self.tanks_count, [t.address for t in self.api_clients])
        while len(self.chosen_tanks) < self.tanks_count:
            self.chosen_tanks = []
            for tank in self.api_clients:
                try:
                    if len(self.chosen_tanks) < self.tanks_count and tank.book(self.exclusive_mode):
                        self.chosen_tanks.append(tank)
                except Exception, exc:
                    self.log.info("Tank %s is unavailable: %s", tank.address, exc.message)
                    self.log.debug("Full exception: %s", traceback.format_exc(exc))

            if len(self.chosen_tanks) < self.tanks_count:
                self.log.info("Not enough tanks available (%s), waiting 5sec before retry...", len(self.chosen_tanks))
                self.log.debug("Releasing booked tanks")
                for tank in self.chosen_tanks:
                    tank.release()
                time.sleep(5)

    def prepare_tanks(self):
        self.log.info("Preparing chosen tanks: %s", [t.address for t in self.chosen_tanks])
        for tank in self.chosen_tanks:
            tank.prepare_test(self.config_file, self.files)
        self.log.debug("Waiting for tanks to be prepared...")
        pending_tanks = [tank for tank in self.chosen_tanks]
        while len(pending_tanks):
            self.log.debug("Waiting tanks: %s", pending_tanks)
            new_pending = []
            for tank in pending_tanks:
                if tank.get_test_status()["status"] != TankAPIClient.PREPARED:
                    new_pending.append(tank)

            pending_tanks = new_pending
            if len(pending_tanks):
                self.log.info("Waiting tanks: %s", [t.address for t in pending_tanks])
                time.sleep(5)
        self.log.debug("Done waiting preparations")

    def download_artifacts(self, tank):
        artifacts = tank.get_test_status()["artifacts"]
        for fname in self.artifacts_to_download:
            for artifact in artifacts:
                if fnmatch.fnmatch(artifact, fname):
                    self.log.info("Downloading artifact from %s: %s...", tank.address, artifact)
                    local_name = self.core.artifacts_base_dir + os.path.sep + artifact
                    tank.download_artifact(artifact, local_name)
                    self.core.add_artifact_file(local_name)