import threading
import time
import six
import pandas as pd
import logging
from yandextank.contrib.netort.netort.data_manager.common.interfaces import Aggregated


if six.PY3:
    from queue import Empty
else:  # six.PY2
    from Queue import Empty


logger = logging.getLogger(__name__)


class MetricsRouter(threading.Thread):
    """
    Drain incoming queue, concatenate dataframes by metric type and process to callbacks
    callback receives resulting dataframe
    """

    # TODO: MetricsRouter should not know anything about DataManager. Pass source and subscribers directly.
    def __init__(self, manager, aggregator_buffer_size=10):
        """
        :param aggregator_buffer_size: seconds
        :type aggregator_buffer_size: int
        :type manager: yandextank.contrib.netort.netort.data_manager.DataManager
        """
        super(MetricsRouter, self).__init__()
        self.aggregator_buffer_size = aggregator_buffer_size
        self.manager = manager
        self._finished = threading.Event()
        self._stopped = threading.Event()
        self._interrupted = threading.Event()
        self.daemon = True  # just in case, bdk+ytank stuck w/o this at join of Drain thread
        self.__buffer = {}

    def run(self):
        while not self._stopped.is_set():
            self.__route()
        logger.info('Router received interrupt signal, routing rest of the data. Qsize: %s',
                    self.manager.routing_queue.qsize())
        while self.manager.routing_queue.qsize() > 1 and not self._interrupted.is_set():
            self.__route()
        self.__route(last_piece=True)
        logger.info('Router finished its work')
        self._finished.set()

    def _from_buffer(self, metric_data, last_piece):
        """
        :type metric_data: yandextank.contrib.netort.netort.data_manager.common.interfaces.MetricData
        :rtype: pd.DataFrame
        """
        buffered = self.__buffer.pop(metric_data.local_id, None)
        df = pd.concat([buffered, metric_data.df]) if buffered is not None else metric_data.df
        if not last_piece:
            cut, new_buf = df[df.second < df.second.max() - Aggregated.buffer_size],\
                df[df.second >= df.second.max() - Aggregated.buffer_size]
            self.__buffer[metric_data.local_id] = new_buf
            return cut
        else:
            return df

    @staticmethod
    def __process_df(df, dtype, local_id):
        processed_df = dtype.processor(df)
        processed_df.loc[:, 'metric_local_id'] = local_id
        return processed_df

    def __route(self, last_piece=False):
        try:
            # metric_data contains only one metric and one/several data_types
            metric_data = self.manager.routing_queue.get_nowait()
        except Empty:
            return
        routed_data = {}
        from_buffer = self._from_buffer(metric_data, last_piece) if metric_data.is_aggregated else metric_data.df
        for dtype in metric_data.data_types:
            unprocessed = from_buffer if dtype.is_aggregated() else metric_data.df
            if not unprocessed.empty:
                processed = self.__process_df(unprocessed, dtype, metric_data.local_id)
                if not processed.empty:
                    routed_data.setdefault(dtype, []).append(processed)

        if last_piece:
            for metric_local_id, df in self.__buffer.items():
                d_types = self.manager.metrics[metric_local_id].data_types
                for dtype in [dt for dt in d_types if dt.is_aggregated()]:
                    processed = self.__process_df(df, dtype, metric_local_id)
                    routed_data.setdefault(dtype, []).append(processed)

        for dtype, dfs in routed_data.items():
            for df in dfs:
                for subscriber in self.manager.callbacks:
                    callback = self.manager.subscribers[subscriber]
                    callback(dtype, df)
            routed_data[dtype] = pd.concat(dfs, sort=False)

        if not self.manager.callbacks:
            logger.debug('No subscribers/callbacks for metrics yet... skipped metrics')
            time.sleep(1)
            return

    def wait(self, timeout=None):
        self._finished.wait(timeout=timeout)

    def close(self):
        self._stopped.set()

    def interrupt(self):
        self.close()
        logger.debug('Routing interrupted')
        self._interrupted.set()
