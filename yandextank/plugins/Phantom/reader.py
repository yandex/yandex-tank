"""
Phantom phout format reader. Read chunks from phout and produce data frames
"""
import pandas as pd
import numpy as np
import logging
import json
import time
import datetime
import itertools as itt
from StringIO import StringIO

logger = logging.getLogger(__name__)

phout_columns = [
    'send_ts', 'tag', 'interval_real', 'connect_time', 'send_time', 'latency',
    'receive_time', 'interval_event', 'size_out', 'size_in', 'net_code',
    'proto_code'
]

dtypes = {
    'time': np.float64,
    'tag': np.str,
    'interval_real': np.int64,
    'connect_time': np.int64,
    'send_time': np.int64,
    'latency': np.int64,
    'receive_time': np.int64,
    'interval_event': np.int64,
    'size_out': np.int64,
    'size_in': np.int64,
    'net_code': np.int64,
    'proto_code': np.int64,
}


def string_to_df(data):
    start_time = time.time()
    chunk = pd.read_csv(
        StringIO(data), sep='\t', names=phout_columns, dtype=dtypes)

    chunk['receive_ts'] = chunk.send_ts + chunk.interval_real / 1e6
    chunk['receive_sec'] = chunk.receive_ts.astype(np.int64)
    # TODO: consider configuration for the following:
    chunk['tag'] = chunk.tag.str.rsplit('#', 1, expand=True)[0]
    chunk.set_index(['receive_sec'], inplace=True)

    logger.debug("Chunk decode time: %.2fms", (time.time() - start_time) * 1000)
    return chunk


class PhantomReader(object):
    def __init__(self, filename, cache_size=1024 * 1024 * 50):
        self.buffer = ""
        self.phout = open(filename, 'r')
        self.closed = False
        self.cache_size = cache_size

    def _read_phout_chunk(self):
        data = self.phout.read(self.cache_size)
        if data:
            parts = data.rsplit('\n', 1)
            if len(parts) > 1:
                ready_chunk = self.buffer + parts[0] + '\n'
                self.buffer = parts[1]
                return string_to_df(ready_chunk)
            else:
                self.buffer += parts[0]
        else:
            self.buffer += self.phout.readline()
        return None

    def __iter__(self):
        while not self.closed:
            yield self._read_phout_chunk()
        yield self._read_phout_chunk()
        self.phout.close()

    def close(self):
        self.closed = True


class PhantomStatsReader(object):
    def __init__(self, filename, phantom_info):
        self.phantom_info = phantom_info
        self.buffer = ""
        self.stat_buffer = ""
        self.stat_filename = filename
        self.closed = False
        self.start_time = 0

    def _decode_stat_data(self, chunk):
        """
        Return all items found in this chunk
        """
        for date_str, statistics in chunk.iteritems():
            date_obj = datetime.datetime.strptime(
                date_str.split(".")[0], '%Y-%m-%d %H:%M:%S')
            chunk_date = int(time.mktime(date_obj.timetuple()))
            instances = 0
            for benchmark_name, benchmark in statistics.iteritems():
                if not benchmark_name.startswith("benchmark_io"):
                    continue
                for method, meth_obj in benchmark.iteritems():
                    if "mmtasks" in meth_obj:
                        instances += meth_obj["mmtasks"][2]

            offset = chunk_date - 1 - self.start_time
            reqps = 0
            if offset >= 0 and offset < len(self.phantom_info.steps):
                reqps = self.phantom_info.steps[offset][0]
            yield {
                'ts': chunk_date - 1,
                'metrics': {
                    'instances': instances,
                    'reqps': reqps
                }
            }

    def _read_stat_data(self, stat_file):
        chunk = stat_file.read(1024 * 1024 * 50)
        if chunk:
            self.stat_buffer += chunk
            parts = self.stat_buffer.rsplit('\n},', 1)
            if len(parts) > 1:
                ready_chunk = parts[0]
                self.stat_buffer = parts[1]
                chunks = [
                    json.loads('{%s}}' % s) for s in ready_chunk.split('\n},')
                ]
                return list(
                    itt.chain(
                        *(self._decode_stat_data(chunk) for chunk in chunks)))
        else:
            self.stat_buffer += stat_file.readline()

    def __iter__(self):
        """
        Union buffer and chunk, split using '\n},',
        return splitted parts
        """
        self.start_time = int(time.time())
        with open(self.stat_filename, 'r') as stat_file:
            while not self.closed:
                yield self._read_stat_data(stat_file)
            yield self._read_stat_data(stat_file)

    def close(self):
        self.closed = True
