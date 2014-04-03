""" Module to perform distributed tests """
# TODO: how to deal with remote monitoring data?
import random

from tankcore import AbstractPlugin
from Tank.API.client import TankAPIClient


class DistributedPlugin(AbstractPlugin):
    SECTION = "distributed"

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.api_clients = {}
        self.api_client_class = TankAPIClient
        self.config_file = None
        self.tanks_count = 1
        self.configs = []
        self.options = []
        self.files = []
        self.download_artifacts = []

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
            self.api_clients[tank] = self.api_client_class(tank, api_port, api_timeout)

        self.config_file = self.compose_load_ini(self.configs, self.options)
        self.core.add_artifact_file(self.config_file)

    def prepare_test(self):
        """ choosing tanks, uploading files, calling configure and prepare """


    def start_test(self):
        """ starting test  """

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