"""
Phantom phout format reader. Read chunks from phout and produce data frames
"""
import pandas as pd
from StringIO import StringIO
import logging

LOG = logging.getLogger(__name__)


phout_columns = [
    'send_ts', 'tag', 'interval_real',
    'connect_time', 'send_time',
    'latency', 'receive_time',
    'interval_event', 'size_out',
    'size_in', 'net_code', 'proto_code']


def string_to_df(data):
    chunk = pd.read_csv(
        StringIO(data),
        sep='\t', names=phout_columns)
    chunk['receive_ts'] = chunk.send_ts + chunk.interval_real / 1e6
    chunk['receive_sec'] = chunk.receive_ts.astype(int)
    chunk.set_index(['receive_sec'], inplace=True)
    return chunk


class PhantomReader(object):
    def __init__(self, filename):
        self.buffer = ""
        self.phout = open(filename, 'r')
        self.closed = False

    def read_chunk(self):
        if self.closed:
            return None
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

    def close(self):
        self.closed = True
        self.phout.close()
