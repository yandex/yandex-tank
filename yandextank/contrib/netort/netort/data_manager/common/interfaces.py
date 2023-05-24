# coding=utf-8
import threading

import pandas as pd

try:
    import queue
except ImportError:
    import Queue as queue
import uuid
import numpy as np
import logging

logger = logging.getLogger(__name__)


class Aggregated(object):
    buffer_size = 10  # seconds

    @classmethod
    def is_aggregated(cls):
        return True


class DataType(object):
    table_name = ''
    columns = []
    is_aggregated = False

    @classmethod
    def processor(cls, df):
        """
        :type df: pandas.DataFrame
        :rtype: pandas.DataFrame
        """
        return df

    @classmethod
    def is_aggregated(cls):
        return False


class TypeTimeSeries(DataType):
    table_name = 'metrics'
    columns = ['ts', 'value']


class TypeEvents(DataType):
    table_name = 'events'
    columns = ['ts', 'value']


class TypeQuantiles(Aggregated, DataType):
    perc_list = [0, 10, 25, 50, 75, 80, 85, 90, 95, 98, 99, 100]
    qlist = ['q%d' % n for n in perc_list]
    rename = {'count': 'cnt', 'mean': 'average', 'std': 'stddev', '0%': 'q0', '10%': 'q10', '25%': 'q25',
              '50%': 'q50', '75%': 'q75', '80%': 'q80', '85%': 'q85', '90%': 'q90',
              '95%': 'q95', '98%': 'q98', '99%': 'q99', '100%': 'q100', }

    table_name = 'aggregates'
    columns = ['ts'] + qlist + ['average', 'stddev', 'sum', 'cnt']
    __aggregator_buffer = {}
    aggregator_buffer_size = 10

    @classmethod
    def processor(cls, df, groupby='second'):
        # result = pd.DataFrame.from_dict({ts: self.aggregates(df) for ts, df in by_second.items()}
        #                                 , orient='index', columns=Aggregate.columns)
        if df.empty:
            logging.debug('Empty df for quantiles, skip %s', df)
            return pd.DataFrame()
        df = df.set_index(groupby)
        series = df.loc[:, AbstractMetric.VALUE_COL]
        res = series.groupby(series.index). \
            describe(percentiles=[i / 100. for i in cls.perc_list]). \
            rename(columns=cls.rename)
        res['ts'] = res.index
        res['cnt'] = res['cnt'].astype(int)
        res['sum'] = res['average'] * res['cnt']
        return res


class TypeDistribution(Aggregated, DataType):
    table_name = 'distributions'
    columns = ['ts', 'l', 'r', 'cnt']
    DEFAULT_BINS = np.concatenate((
        np.linspace(0, 4990, 500, dtype=int),  # 10µs accuracy
        np.linspace(5000, 9900, 50, dtype=int),  # 100µs accuracy
        np.linspace(10, 499, 490, dtype=int) * 1000,  # 1ms accuracy
        np.linspace(500, 2995, 500, dtype=int) * 1000,  # 5ms accuracy
        np.linspace(3000, 9990, 700, dtype=int) * 1000,  # 10ms accuracy
        np.linspace(10000, 29950, 400, dtype=int) * 1000,  # 50ms accuracy
        np.linspace(30000, 119900, 900, dtype=int) * 1000,  # 100ms accuracy
        np.linspace(120, 300, 181, dtype=int) * 1000000  # 1s accuracy
    ))

    @classmethod
    def processor(cls, df, bins=DEFAULT_BINS, groupby='second'):
        if df.empty:
            logger.debug('Empty df for distribution, skip %s', df)
            return pd.DataFrame()
        df = df.set_index(groupby)
        series = df.loc[:, AbstractMetric.VALUE_COL]
        data = {ts: np.histogram(s, bins=bins) for ts, s in series.groupby(series.index)}
        # data, bins = np.histogram(series, bins=bins)
        result = pd.concat(
            [pd.DataFrame({'l': bins[:-1],
                           'r': bins[1:],
                           'cnt': cnt,
                           'ts': ts},
                          columns=['l', 'r', 'cnt', 'ts']
                          ).query('cnt > 0') for ts, (cnt, bins) in data.items()]
        )
        return result


class TypeHistogram(Aggregated, DataType):
    table_name = 'histograms'
    columns = ['ts', 'category', 'cnt']

    @classmethod
    def processor(cls, df, groupby='second'):
        if df.empty:
            logger.debug('Empty df for histogram, skip %s', df)
            return pd.DataFrame()
        df = df.set_index(groupby)
        series = df.loc[:, AbstractMetric.VALUE_COL]
        data = series.groupby([series.index, series.values]).size().reset_index(). \
            rename(columns={'second': 'ts', 'level_1': 'category', 'value': 'cnt'})
        return data


class AbstractClient(object):
    def __init__(self, meta, data_session):
        self.local_id = "client_{uuid}".format(uuid=uuid.uuid4())
        self.pending_metrics = []
        self.data_session = data_session
        self.pending_queue = queue.Queue()
        self.meta = meta

    def subscribe(self, metric):
        self.pending_metrics.append(metric)

    def put(self, data_type, df):
        self.pending_queue.put((data_type, df))

    def update_job(self, meta):
        pass

    def update_metric(self, meta):
        pass


class MetricData(object):
    def __init__(self, df, data_types, local_id, test_start):
        """

        :param df: pandas.DataFrame
        :param data_types: list of DataType
        :param local_id: uuid4
        """
        df.loc[:, 'metric_local_id'] = local_id
        df = df.set_index('metric_local_id')
        self.data_types = data_types
        self.local_id = local_id
        df.loc[:, 'ts'] = (df['ts'] - test_start).astype(int)
        if self.is_aggregated:
            df.loc[:, 'second'] = (df['ts'] / 1000000).astype(int)
        self.df = df

    @property
    def is_aggregated(self):
        return any([dtype.is_aggregated() for dtype in self.data_types])

    def __repr__(self):
        return "MetricData: aggregated={}, data types={}\n{}".format(
            'yes' if self.is_aggregated else 'no',
            self.data_types.__repr__(),
            self.df.__repr__()
        )


class AbstractMetric(object):
    VALUE_COL = 'value'
    TS_COL = 'ts'

    def __init__(self, meta, _queue, test_start, raw=True, aggregate=False, parent=None, case=None):
        self.local_id = str(uuid.uuid4())
        self.meta = meta
        self.routing_queue = _queue
        self.test_start = test_start
        self.raw = raw
        self.aggregate = aggregate
        self.parent = parent
        self.case = case
        if not (raw or aggregate):
            raise ValueError('Either raw or aggregate must be True to upload some data')

    @property
    def type(self):
        """
        :rtype: DataType
        """
        raise NotImplementedError('Abstract type property should be redefined!')

    @property
    def aggregate_types(self):
        """
        :rtype: list of DataType
        """
        raise NotImplementedError('Abstract type property should be redefined!')

    @property
    def data_types(self):
        """
        :rtype: list of DataType
        """
        return [self.type] * self.raw + self.aggregate_types * self.aggregate

    def put(self, df):
        # FIXME check dtypes of an incoming dataframe
        data = MetricData(df, self.data_types, self.local_id, self.test_start)
        self.routing_queue.put(data)


class QueueWorker(threading.Thread):
    """ Process data """

    def __init__(self, _queue):
        """
        :type _queue: queue.Queue
        """
        super(QueueWorker, self).__init__()
        self.queue = _queue
        self._finished = threading.Event()
        self._stopped = threading.Event()
        self._interrupted = threading.Event()

    def stop(self):
        self._stopped.set()

    def interrupt(self):
        self._stopped.set()
        self._interrupted.set()

    def run(self):
        while not self._stopped.is_set():
            self._process_pending_queue()
        while self.queue.qsize() > 0 and not self._interrupted.is_set():
            self._process_pending_queue(progress=True)
        while self.queue.qsize() > 0:
            self.queue.get_nowait()
        self._finished.set()

    def _process_pending_queue(self, progress=False):
        raise NotImplementedError

    def is_finished(self):
        return self._finished.is_set()
