"""
Phantom phout format reader. Read chunks from phout and produce data frames
"""
import pandas as pd
from StringIO import StringIO
import logging
import json
import time
import datetime

LOG = logging.getLogger(__name__)

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

        def __read_stat_data(self):
            """ Read active instances info """
            end_marker = "\n},"
            self.stat_read_buffer += self.stat.read()
            while end_marker in self.stat_read_buffer:
                chunk_str = self.stat_read_buffer[
                    :self.stat_read_buffer.find(end_marker) + len(end_marker) - 1]
                self.stat_read_buffer = self.stat_read_buffer[
                    self.stat_read_buffer.find(end_marker) + len(
                        end_marker) + 1:]
                chunk = json.loads("{%s}" % chunk_str)
                self.log.debug("Stat chunk (left %s bytes): %s",
                               len(self.stat_read_buffer), chunk)

                for date_str in chunk.keys():
                    statistics = chunk[date_str]

                    date_obj = datetime.datetime.strptime(
                        date_str.split(".")[0], '%Y-%m-%d %H:%M:%S')
                    pending_datetime = int(time.mktime(date_obj.timetuple()))
                    self.stat_data[pending_datetime] = 0

                    for benchmark_name in statistics.keys():
                        if not benchmark_name.startswith("benchmark_io"):
                            continue
                        benchmark = statistics[benchmark_name]
                        for method in benchmark:
                            meth_obj = benchmark[method]
                            if "mmtasks" in meth_obj:
                                self.stat_data[pending_datetime] += meth_obj[
                                    "mmtasks"][2]
                    self.log.debug("Active instances: %s=>%s",
                                   pending_datetime,
                                   self.stat_data[pending_datetime])

            self.log.debug(
                "Instances info buffer size: %s / Read buffer size: %s",
                len(self.stat_data), len(self.stat_read_buffer))

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
                yield json.loads('{%s}}' % m)
        else:
            self.stat_buffer += parts[0]

    def close(self):
        self.closed = True
        self.stat.close()
