""" Module to perform distributed tests """
# TODO: how to deal with remote monitoring data?
from tankcore import AbstractPlugin
from Tank.API.client import TankAPIClient


class DistributedPlugin(AbstractPlugin):
    SECTION = "distributed"

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.api_client_class = TankAPIClient

        self.api_port = 8003
        self.api_timeout = 5
        self.tanks_pool = []
        self.tanks_count = 1
        self.random_tanks = 0
        self.configs = []
        self.options = []
        self.files = []
        self.download_artifacts = []

    def get_available_options(self):
        return ["api_port", "api_timeout",
                "tanks_pool", "tanks_count", "random_tanks",
                "configs", "options", "files", "download_artifacts"]

    def configure(self):
        self.api_port = int(self.get_option("api_port", self.api_port))
        self.api_timeout = int(self.get_option("api_timeout", self.api_timeout))

        self.tanks_pool = self.get_multiline_option("tanks_pool")
        count = self.get_option("tanks_count", self.tanks_count)
        if count == 'all':
            self.tanks_count = len(self.tanks_pool)
        else:
            self.tanks_count = int(count)

        self.random_tanks = int(self.get_option("random_tanks", self.random_tanks))

        self.configs = self.get_multiline_option("configs")
        self.options = self.get_multiline_option("options", self.options)
        self.files = self.get_multiline_option("files", self.files)
        self.download_artifacts = self.get_multiline_option("download_artifacts", self.download_artifacts)

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

