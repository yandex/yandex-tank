""" Module to perform distributed tests """
# TODO: how to deal with remote monitoring data?
import random
import time

from tankcore import AbstractPlugin
from Tank.API.client import TankAPIClient


class DistributedPlugin(AbstractPlugin):
    SECTION = "distributed"

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        # config options
        self.tanks_count = 1
        self.configs = []
        self.options = []
        self.files = []
        self.download_artifacts = []
        self.chosen_tanks = []

        # regular members
        self.api_clients = []
        self.api_client_class = TankAPIClient
        self.config_file = None


    def get_available_options(self):
        return ["api_port", "api_timeout",
                "tanks_pool", "tanks_count", "random_tanks",
                "configs", "options", "files", "download_artifacts"]

    def configure(self):
        api_port = int(self.get_option("api_port", 8003))
        api_timeout = int(self.get_option("api_timeout", 5))

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
        self.download_artifacts = self.get_multiline_option("download_artifacts", self.download_artifacts)

        # done reading options, do some preparations

        for tank in tanks_pool:
            self.api_clients.append(self.api_client_class(tank, api_port, api_timeout))

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

    def is_test_finished(self):
        """ polling for the status of remote jobs """
        return AbstractPlugin.is_test_finished(self)

    def end_test(self, retcode):
        """ call graceful shutdown for all tests """
        return AbstractPlugin.end_test(self, retcode)

    def post_process(self, retcode):
        """ download artifacts """
        return AbstractPlugin.post_process(self, retcode)

    @staticmethod
    def get_key():
        return __file__

    def compose_load_ini(self, configs, options):
        fname = self.core.mkstemp('.ini', 'load_')
        return fname

    def choose_tanks(self):
        self.log.info("Choosing %s tanks from pool: %s", self.tanks_count, [t.address for t in self.api_clients])
        while len(self.chosen_tanks) < self.tanks_count:
            self.chosen_tanks = []
            for tank in self.api_clients:
                if len(self.chosen_tanks) < self.tanks_count and tank.book():
                    self.chosen_tanks.append(tank)

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
                if tank.get_status() != TankAPIClient.PREPARED:
                    new_pending.append(tank)

            pending_tanks = new_pending
            if len(pending_tanks):
                self.log.info("Waiting tanks: %s", [t.address for t in pending_tanks])
                time.sleep(5)
        self.log.debug("Done waiting preparations")

