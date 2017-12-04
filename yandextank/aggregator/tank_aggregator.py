""" Core module to calculate aggregate data """
import json
import logging

import queue as q
from pkg_resources import resource_string

from .aggregator import Aggregator, DataPoller
from .chopper import TimeChopper
from yandextank.common.interfaces import AggregateResultListener
from yandextank.common.util import Drain, Chopper

logger = logging.getLogger(__name__)


class LoggingListener(AggregateResultListener):
    """ Log aggregated results """

    def on_aggregated_data(self, data, stats):
        logger.info("Got aggregated sample:\n%s", json.dumps(data, indent=2))
        logger.info("Stats:\n%s", json.dumps(stats, indent=2))


def get_from_queue(queue):
    data = []
    for _ in range(queue.qsize()):
        try:
            data.append(queue.get_nowait())
        except q.Empty:
            break
    return data


class TankAggregator(object):
    """
    Plugin that manages aggregation and stats collection
    """

    SECTION = 'aggregator'

    @staticmethod
    def get_key():
        return __file__

    def __init__(self, generator):
        # AbstractPlugin.__init__(self, core, cfg)
        """

        :type generator: GeneratorPlugin
        """
        self.generator = generator
        self.listeners = []  # [LoggingListener()]
        self.results = q.Queue()
        self.stats = q.Queue()
        self.data_cache = {}
        self.stat_cache = {}

    def start_test(self):
        self.reader = self.generator.get_reader()
        self.stats_reader = self.generator.get_stats_reader()
        aggregator_config = json.loads(
            resource_string(__name__, 'config/phout.json').decode('utf8'))
        verbose_histogram = True
        if verbose_histogram:
            logger.info("using verbose histogram")
        if self.reader and self.stats_reader:
            pipeline = Aggregator(
                TimeChopper(
                    DataPoller(source=self.reader, poll_period=1),
                    cache_size=3),
                aggregator_config,
                verbose_histogram)
            self.drain = Drain(pipeline, self.results)
            self.drain.start()
            self.stats_drain = Drain(
                Chopper(DataPoller(
                    source=self.stats_reader, poll_period=1)),
                self.stats)
            self.stats_drain.start()
        else:
            logger.warning("Generator not found. Generator must provide a reader and a stats_reader interface")

    def _collect_data(self):
        """
        Collect data, cache it and send to listeners
        """
        data = get_from_queue(self.results)
        stats = get_from_queue(self.stats)
        logger.debug("Data timestamps:\n%s" % [d.get('ts') for d in data])
        logger.debug("Stats timestamps:\n%s" % [d.get('ts') for d in stats])
        for item in data:
            ts = item['ts']
            if ts in self.stat_cache:
                # send items
                data_item = item
                stat_item = self.stat_cache.pop(ts)
                self.__notify_listeners(data_item, stat_item)
            else:
                self.data_cache[ts] = item
        for item in stats:
            ts = item['ts']
            if ts in self.data_cache:
                # send items
                data_item = self.data_cache.pop(ts)
                stat_item = item
                self.__notify_listeners(data_item, stat_item)
            else:
                self.stat_cache[ts] = item

    def is_test_finished(self):
        self._collect_data()
        return -1

    def end_test(self, retcode):
        retcode = self.generator.end_test(retcode)
        if self.reader:
            self.reader.close()
        if self.stats_reader:
            self.stats_reader.close()
        if self.drain:
            self.drain.join()
        if self.stats_drain:
            self.stats_drain.join()
        self._collect_data()
        return retcode

    def add_result_listener(self, listener):
        self.listeners.append(listener)

    def __notify_listeners(self, data, stats):
        """ notify all listeners about aggregate data and stats """
        for listener in self.listeners:
            listener.on_aggregated_data(data, stats)
