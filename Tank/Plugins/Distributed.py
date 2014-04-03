""" Module to perform distributed tests """
from tankcore import AbstractPlugin


class LoadosophiaPlugin(AbstractPlugin):
    def __init__(self, core):
        AbstractPlugin.__init__(self, core)

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        return ["api_port",
                "tanks_pool", "tanks_count", "random_tanks",
                "configs", "options", "files", "download_artifacts"]

    def configure(self):
        AbstractPlugin.configure(self)

    def prepare_test(self):
        AbstractPlugin.prepare_test(self)

    def start_test(self):
        AbstractPlugin.start_test(self)

    def is_test_finished(self):
        return AbstractPlugin.is_test_finished(self)

    def end_test(self, retcode):
        return AbstractPlugin.end_test(self, retcode)

    def post_process(self, retcode):
        return AbstractPlugin.post_process(self, retcode)