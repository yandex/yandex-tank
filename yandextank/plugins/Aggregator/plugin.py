""" Core module to calculate aggregate data """
import logging

from pkg_resources import resource_string
import json
import Queue as q
from yandextank.core import AbstractPlugin
from yandextank.core.util import Drain
from yandextank.core.exceptions import PluginImplementationError
from aggregator import Aggregator, DataPoller
from chopper import TimeChopper


LOG = logging.getLogger(__name__)


class AggregateResultListener(object):
    """ Listener interface """

    def on_aggregated_data(self, data):
        """ notification about new aggregated data """
        raise NotImplementedError("Abstract method needs to be overridden")


class LoggingListener(AggregateResultListener):
    """ Log aggregated results """

    def on_aggregated_data(self, data):
        LOG.info("Got aggregated sample:\n%s", json.dumps(data, indent=2))


class AggregatorPlugin(AbstractPlugin):
    """ Plugin that manages aggregation """

    SECTION = 'aggregate'

    @staticmethod
    def get_key():
        return __file__

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.listeners = [LoggingListener()]
        self.reader = None
        self.results = q.Queue()

    def get_available_options(self):
        return []

    def configure(self):
        self.aggregator_config = json.loads(
            resource_string(__name__, 'config/phout.json'))

    def start_test(self):
        if self.reader:
            pipeline = Aggregator(
                TimeChopper(
                    DataPoller(
                        source=self.reader,
                        poll_period=1),
                    cache_size=3),
                self.aggregator_config
            )
            self.drain = Drain(pipeline, self.results)
            self.drain.start()
        else:
            raise PluginImplementationError(
                "Generator must pass a Reader to Aggregator before starting test")

    def is_test_finished(self):
        data = []
        for _ in range(self.results.qsize()):
            try:
                data.append(self.results.get_nowait())
            except q.Empty:
                break
        if data:
            self.__notify_listeners(data)
        return -1

    def end_test(self, retcode):
        if self.drain:
            self.drain.close()
        # read all data left here
        return retcode

    def close(self):
        if self.reader:
            self.reader.close()

    def add_result_listener(self, listener):
        self.listeners.append(listener)

    def __notify_listeners(self, data):
        """ notify all listeners about aggregate data """
        for listener in self.listeners:
            listener.on_aggregated_data(data)
