import numpy as np
import time
from collections import Counter


phout_columns = [
    'time', 'tag', 'interval_real',
    'connect_time', 'send_time',
    'latency', 'receive_time',
    'interval_event', 'size_out',
    'size_in', 'net_code', 'proto_code']

phantom_config = {
    "interval_real": ["total", "max", "min", "hist", "len"],
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
    def __init__(self, config):
        bins = np.linspace(0, 4990, 500)
        bins = np.append(bins, np.linspace(5000, 9900, 50))
        bins = np.append(bins, np.linspace(10, 499, 490) * 1000)
        bins = np.append(bins, np.linspace(500, 2995, 500) * 1000)
        bins = np.append(bins, np.linspace(3000, 9990, 700) * 1000)
        bins = np.append(bins, np.linspace(10000, 30000, 401) * 1000)

        self.bins = bins
        self.percentiles = np.array([50, 75, 80, 85, 90, 95, 99])
        self.config = config
        self.aggregators = {
            "hist": self._histogram,
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
        while True:
            chunk = self.source.read_chunk()
            if chunk is not None:
                yield chunk
            time.sleep(self.poll_period)


class Aggregator(object):
    def __init__(self, source, config):
        self.worker = Worker(config)
        self.source = source
        self.groupby = 'tag'

    def __iter__(self):
        for ts, chunk in self.source:
            by_tag = list(chunk.groupby([self.groupby]))
            if len(by_tag):
                for tag, data in by_tag:
                    yield {
                        'tag': tag,
                        'ts': ts,
                        'metrics': self.worker.aggregate(data),
                    }
            else:
                yield {
                    'tag': '',
                    'ts': ts,
                    'metrics': self.worker.aggregate(chunk),
                }
