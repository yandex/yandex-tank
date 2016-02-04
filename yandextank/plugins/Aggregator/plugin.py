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

    def on_aggregated_data(self, data, stats):
        """
        notification about new aggregated data and stats

        data contains aggregated metrics and stats contain non-aggregated
        metrics from gun (like instances count, for example)

        data and stats are NOT synchronized and you can get different
        timestamps here and there. If you need to synchronize them, you
        should cache them in your plugin
        """
        raise NotImplementedError("Abstract method needs to be overridden")


class LoggingListener(AggregateResultListener):
    """ Log aggregated results """

    def on_aggregated_data(self, data, stats):
        LOG.info("Got aggregated sample:\n%s", json.dumps(data, indent=2))
        LOG.info("Stats:\n%s", json.dumps(stats, indent=2))


class AggregatorPlugin(AbstractPlugin):
    """
    Plugin that manages aggregation and stats collection
    """

    SECTION = 'aggregate'

    @staticmethod
    def get_key():
        return __file__

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.listeners = []  # [LoggingListener()]
        self.reader = None
        self.stats_reader = None
        self.results = q.Queue()
        self.stats = q.Queue()

    def get_available_options(self):
        return []

    def configure(self):
        self.aggregator_config = json.loads(resource_string(
            __name__, 'config/phout.json'))

    def start_test(self):
        if self.reader and self.stats_reader:
            pipeline = Aggregator(
                TimeChopper(
                    DataPoller(source=self.reader,
                               poll_period=1),
                    cache_size=3),
                self.aggregator_config)
            self.drain = Drain(pipeline, self.results)
            self.drain.start()
            self.stats_drain = Drain(
                DataPoller(source=self.stats_reader,
                           poll_period=1),
                self.stats)
            self.stats_drain.start()
        else:
            raise PluginImplementationError(
                "Generator must pass a Reader and a StatsReader to Aggregator before starting test")

    def is_test_finished(self):
        data = []
        for _ in range(self.results.qsize()):
            try:
                data.append(self.results.get_nowait())
            except q.Empty:
                break
        stats = []
        for _ in range(self.stats.qsize()):
            try:
                stats.append(self.stats.get_nowait())
            except q.Empty:
                break
        if data or stats:
            self.__notify_listeners(data, stats)
        return -1

    def end_test(self, retcode):
        if self.drain:
            self.drain.close()
        if self.stats_drain:
            self.stats_drain.close()
        # read all data left here
        return retcode

    def close(self):
        if self.reader:
            self.reader.close()
        if self.stats_reader:
            self.stats_reader.close()

    def add_result_listener(self, listener):
        self.listeners.append(listener)

    def __notify_listeners(self, data, stats):
        """ notify all listeners about aggregate data and stats """
        for listener in self.listeners:
            listener.on_aggregated_data(data, stats)
