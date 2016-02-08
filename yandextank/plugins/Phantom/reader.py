"""
Phantom phout format reader. Read chunks from phout and produce data frames
"""
import pandas as pd
from StringIO import StringIO
import logging
import json
import time
import datetime

logger = logging.getLogger(__name__)

phout_columns = [
    'send_ts', 'tag', 'interval_real', 'connect_time', 'send_time', 'latency',
    'receive_time', 'interval_event', 'size_out', 'size_in', 'net_code',
    'proto_code'
]


def string_to_df(data):
    chunk = pd.read_csv(StringIO(data), sep='\t', names=phout_columns)
    chunk['receive_ts'] = chunk.send_ts + chunk.interval_real / 1e6
    chunk['receive_sec'] = chunk.receive_ts.astype(int)
    # TODO: consider configuration for the following:
    chunk['tag'] = chunk.tag.str.rsplit('#', 1, expand=True)[0]
    chunk.set_index(['receive_sec'], inplace=True)
    return chunk


class PhantomReader(object):
    def __init__(self, filename):
        self.buffer = ""
        self.stat_buffer = ""
        self.phout = open(filename, 'r')
        self.closed = False

    def next(self):
        if self.closed:
            raise StopIteration
        data = self.phout.read(1024 * 1024 * 10)
        if data:
            parts = data.rsplit('\n', 1)
            if len(parts) > 1:
                ready_chunk = self.buffer + parts[0] + '\n'
                self.buffer = parts[1]
                return string_to_df(ready_chunk)
            else:
                self.buffer += parts[0]
        else:
            self.phout.readline()
        return None

    def __iter__(self):
        return self

    def close(self):
        self.closed = True
        self.phout.close()


class PhantomStatsReader(object):
    def __init__(self, filename):
        self.buffer = ""
        self.stat_buffer = ""
        self.stat = open(filename, 'r')
        self.closed = False

    def __decode_stat_data(self, chunk):
        print(chunk)
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
            logger.debug("Active instances: %s=>%s", chunk_date, instances)
            return {'ts': chunk_date,
                    'metrics': {'instances': instances,
                                'reqps': 0}}

    def __iter__(self):
        """
        Union buffer and chunk, split using '\n},',
        return splitted parts
        """
        chunk = self.stat.read(1024 * 1024 * 10)
        parts = chunk.rsplit('\n},', 1)
        if len(parts) > 1:
            ready_chunk = self.stat_buffer + parts[0]
            self.stat_buffer = parts[1]
            for m in ready_chunk.split('\n},'):
                yield self.__decode_stat_data(json.loads('{%s}}' % m))
        else:
            self.stat_buffer += parts[0]

    def close(self):
        self.closed = True
        self.stat.close()
