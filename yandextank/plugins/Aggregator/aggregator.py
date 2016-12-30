# -*- coding: UTF-8 -*-
import logging
import numpy as np
import time
from collections import Counter

logger = logging.getLogger(__name__)

phout_columns = [
    'time', 'tag', 'interval_real', 'connect_time', 'send_time', 'latency',
    'receive_time', 'interval_event', 'size_out', 'size_in', 'net_code',
    'proto_code'
]

phantom_config = {
    "interval_real": ["total", "max", "min", "hist", "q", "len"],
    "connect_time": ["total", "max", "min", "len"],
    "send_time": ["total", "max", "min", "len"],
    "latency": ["total", "max", "min", "len"],
    "receive_time": ["total", "max", "min", "len"],
    "interval_event": ["total", "max", "min", "len"],
    "size_out": ["total", "max", "min", "len"],
    "size_in": ["total", "max", "min", "len"],
    "net_code": ["count"],
    "proto_code": ["count"],
}


class Worker(object):
    """
    Aggregate Pandas dataframe or dict with numpy ndarrays in it
    """

    def __init__(self, config, verbose_histogram):
        if verbose_histogram:
            bins = np.linspace(0, 4990, 500)  # 10µs accuracy
            bins = np.append(bins,
                             np.linspace(5000, 9900, 50))  # 100µs accuracy
            bins = np.append(bins,
                             np.linspace(10, 499, 490) * 1000)  # 1ms accuracy
            bins = np.append(bins,
                             np.linspace(500, 2995, 500) * 1000)  # 5ms accuracy
            bins = np.append(bins, np.linspace(3000, 9990, 700) *
                             1000)  # 10ms accuracy
            bins = np.append(bins, np.linspace(10000, 29950, 400) *
                             1000)  # 50ms accuracy
            bins = np.append(bins, np.linspace(30000, 119900, 900) *
                             1000)  # 100ms accuracy
            bins = np.append(bins, np.linspace(120, 300, 181) *
                             1000000)  # 1s accuracy
        else:
            # yapf: disable
            bins = np.array([
                0, 1, 2, 3, 4, 5, 6, 7, 8, 9,
                10, 20, 30, 40, 50, 60, 70, 80, 90,
                100, 150, 200, 250, 300, 350, 400, 450,
                500, 600, 650, 700, 750, 800, 850, 900, 950,
                1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500,
                5000, 5500, 6000, 6500, 7000, 7500, 8000, 8500, 9000, 9500, 10000, 11000,
                12000, 13000, 14000, 15000, 20000, 25000, 30000, 35000, 40000, 45000, 50000,
                55000, 60000,
            ]) * 1000
            # yapf: enable

        self.bins = bins
        self.percentiles = np.array([50, 75, 80, 85, 90, 95, 98, 99, 100])
        self.config = config
        self.aggregators = {
            "hist": self._histogram,
            "q": self._quantiles,
            "mean": self._mean,
            "total": self._total,
            "min": self._min,
            "max": self._max,
            "count": self._count,
            "len": self._len,
        }

    def _histogram(self, series):
        data, bins = np.histogram(series, bins=self.bins)
        mask = data > 0
        return {
            "data": [e.item() for e in data[mask]],
            "bins": [e.item() for e in bins[1:][mask]],
        }

    def _mean(self, series):
        return series.mean().item()

    def _total(self, series):
        return series.sum().item()

    def _max(self, series):
        return series.max().item()

    def _min(self, series):
        return series.min().item()

    def _count(self, series):
        return {str(k): v for k, v in dict(Counter(series)).items()}

    def _len(self, series):
        return len(series)

    def _quantiles(self, series):
        return {
            "q": list(self.percentiles),
            "value": list(np.percentile(series, self.percentiles)),
        }

    def aggregate(self, data):
        return {
            key: {
                aggregate: self.aggregators.get(aggregate)(data[key])
                for aggregate in self.config[key]
            }
            for key in self.config
        }


class DataPoller(object):
    def __init__(self, source, poll_period):
        self.poll_period = poll_period
        self.source = source

    def __iter__(self):
        for chunk in self.source:
            if chunk is not None:
                yield chunk
            time.sleep(self.poll_period)


class Aggregator(object):
    def __init__(self, source, config, verbose_histogram):
        self.worker = Worker(config, verbose_histogram)
        self.source = source
        self.groupby = 'tag'

    def __iter__(self):
        for ts, chunk in self.source:
            by_tag = list(chunk.groupby([self.groupby]))
            start_time = time.time()
            result = {
                "ts": ts,
                "tagged":
                {tag: self.worker.aggregate(data)
                 for tag, data in by_tag},
                "overall": self.worker.aggregate(chunk),
            }
            logger.debug(
                "Aggregation time: %.2fms", (time.time() - start_time) * 1000)
            yield result
