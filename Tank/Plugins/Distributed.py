""" Module to perform distributed tests """
from tankcore import AbstractPlugin
from Tank.API.client import TankAPIClient


class DistributedPlugin(AbstractPlugin):
    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.api_client_class = TankAPIClient

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        return ["api_port", "api_timeout",
                "tanks_pool", "tanks_count", "random_tanks",
                "configs", "options", "files", "download_artifacts"]

    def configure(self):
        AbstractPlugin.configure(self)

    def prepare_test(self):
        """ choosing tanks, uploading artifacts, calling configure and prepare """

    def start_test(self):
        """ starting test  """

    def is_test_finished(self):
        """ polling for status """
        return AbstractPlugin.is_test_finished(self)

    def end_test(self, retcode):
        return AbstractPlugin.end_test(self, retcode)

    def post_process(self, retcode):
        return AbstractPlugin.post_process(self, retcode)