""" Core module to calculate aggregate data """
import json
import logging
import queue as q

from pkg_resources import resource_string
from typing import Collection

from .aggregator import Aggregator, data_poller
from .chopper import TimeChopper
from yandextank.common.interfaces import AggregateResultListener, StatsReader

from netort.data_processing import Drain, Chopper, get_nowait_from_queue

logger = logging.getLogger(__name__)


class LoggingListener(AggregateResultListener):
    """ Log aggregated results """

    def on_aggregated_data(self, data, stats):
        logger.info("Got aggregated sample:\n%s", json.dumps(data, indent=2))
        logger.info("Stats:\n%s", json.dumps(stats, indent=2))


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
        self.stats_results = q.Queue()
        self.data_cache = {}
        self.stat_cache = {}
        self.reader = None
        self.stats_reader = None
        self.drain = None
        self.stats_drain = None

    @staticmethod
    def load_config():
        return json.loads(resource_string(__name__, 'config/phout.json').decode('utf8'))

    def start_test(self, poll_period=0.5):
        self.reader = self.generator.get_reader()
        self.stats_reader = self.generator.get_stats_reader()
        aggregator_config = self.load_config()
        verbose_histogram = True
        if verbose_histogram:
            logger.info("using verbose histogram")
        if self.reader and self.stats_reader:
            pipeline =\
                Aggregator(TimeChopper([data_poller(source=r, poll_period=poll_period) for r in self.reader]),
                           aggregator_config,
                           verbose_histogram) \
                if isinstance(self.reader, Collection) else \
                Aggregator(TimeChopper([data_poller(source=self.reader, poll_period=poll_period)]),
                           aggregator_config,
                           verbose_histogram)
            self.drain = Drain(pipeline, self.results)
            self.drain.start()
            self.stats_drain = Drain(
                Chopper(data_poller(
                    source=self.stats_reader, poll_period=poll_period)),
                self.stats_results)
            self.stats_drain.start()
        else:
            logger.warning("Generator not found. Generator must provide a reader and a stats_reader interface")

    def _collect_data(self, end=False):
        """
        Collect data, cache it and send to listeners
        """
        data = get_nowait_from_queue(self.results)
        stats = get_nowait_from_queue(self.stats_results)
        logger.debug("Data timestamps: %s" % [d.get('ts') for d in data])
        logger.debug("Stats timestamps: %s" % [d.get('ts') for d in stats])
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
        if end and len(self.data_cache) > 0:
            logger.info('Timestamps without stats:')
            for ts, data_item in sorted(self.data_cache.items(), key=lambda i: i[0]):
                logger.info(ts)
                self.__notify_listeners(data_item, StatsReader.stats_item(ts, 0, 0))

    def is_aggr_finished(self):
        return self.drain._finished.is_set() and self.stats_drain._finished.is_set()

    def is_test_finished(self):
        self._collect_data()
        return -1

    def end_test(self, retcode):
        retcode = self.generator.end_test(retcode)
        if self.stats_reader:
            logger.info('Closing stats reader')
            self.stats_reader.close()
        if self.drain:
            logger.info('Waiting for gun drain to finish')
            self.drain.join()
            logger.info('Waiting for stats drain to finish')
            self.stats_drain.join()
        logger.info('Collecting remaining data')
        self._collect_data(end=True)
        return retcode

    def add_result_listener(self, listener):
        self.listeners.append(listener)

    def __notify_listeners(self, data, stats):
        """ notify all listeners about aggregate data and stats """
        for listener in self.listeners:
            listener.on_aggregated_data(data, stats)
