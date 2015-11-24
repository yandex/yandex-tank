import time
import unittest
import pandas as pd

from yandextank.plugins.NumpyAggregator.chopper import TimeChopper
from yandextank.plugins.NumpyAggregator.aggregator import Worker, Aggregator


phout_columns = [
    'send_ts', 'tag', 'interval_real',
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


class TimeChopperTestCase(unittest.TestCase):
    def setUp(self):
        self.chopper = TimeChopper(PhantomReader("data/phout_example.txt"), 3)

    def test_chop(self):
        chunks = list(self.chopper)
        self.assertEquals(6, len(chunks))
        seconds_ts = [set(chunk.receive_ts.astype(int)) for _, chunk in chunks]
        # check all chunk entries contain timestamps from same second
        for timestamps in seconds_ts:
            self.assertEquals(1, len(timestamps))

        #check we have no repeated timestamps
        self.assertEquals(
            len(seconds_ts),
            len(set(ts for tsl in seconds_ts for ts in tsl)))


class WorkerTestCase(unittest.TestCase):
    def setUp(self):
        self.chopper = TimeChopper(PhantomReader("data/phout_example.txt"), 3)

    def test_worker(self):
        worker = Worker(phantom_config)
        for _, chunk in self.chopper:
            print(worker.aggregate(chunk))

    def test_aggregator(self):
        aggregator = Aggregator(self.chopper, phantom_config)
        for result in aggregator:
            print(result)


class PhantomReader(object):
    def __init__(self, filename):
        self.data_source = pd.read_csv(
            filename,
            sep='\t', names=phout_columns,
            chunksize=10,
        )

    def __iter__(self):
        for chunk in self.data_source:
            chunk['receive_ts'] = chunk.send_ts + chunk.interval_real / 1e6
            chunk['receive_sec'] = chunk.receive_ts.astype(int)
            chunk.set_index(['receive_sec'], inplace=True)
            yield chunk

if __name__ == '__main__':
    unittest.main()
