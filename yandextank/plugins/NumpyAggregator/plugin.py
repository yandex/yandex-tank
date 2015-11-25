""" Core module to calculate aggregate data """
import logging

from yandextank.core import AbstractPlugin


LOG = logging.getLogger(__name__)


class AggregateResultListener(object):
    """ Listener interface """

    def on_aggregated_data(self, data):
        """ notification about new aggregated data """
        raise NotImplementedError("Abstract method needs to be overridden")


class NumpyAggregatorPlugin(AbstractPlugin):
    """ Plugin that manages aggregation """

    SECTION = 'aggregator'

    @staticmethod
    def get_key():
        return __file__

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.listeners = []

    def get_available_options(self):
        return []

    def configure(self):
        pass

    def start_test(self):
        pass

    def is_test_finished(self):
        pass
        # aggregate some data
        return -1

    def end_test(self, retcode):
        pass
        # read all data left here
        return retcode

    def add_result_listener(self, listener):
        self.listeners.append(listener)

    def __notify_listeners(self, data):
        """ notify all listeners about aggregate data """
        for listener in self.listeners:
            listener.on_aggregated_data(data)
