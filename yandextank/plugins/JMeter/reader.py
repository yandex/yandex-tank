import os
import json
import pandas as pd
import numpy as np
import time
from StringIO import StringIO
import yandextank.plugins.Aggregator.aggregator as agg
from yandextank.plugins.Aggregator.chopper import TimeChopper
import Queue as q
import logging

logger = logging.getLogger(__name__)

KNOWN_EXC = {
    "java.net.NoRouteToHostException": 113,
    "java.net.ConnectException": 110,
    "java.net.BindException": 99,
    "java.net.PortUnreachableException": 101,
    "java.net.ProtocolException": 71,
    "java.net.SocketException": 32,
    "java.net.SocketTimeoutException": 110,
    "java.net.UnknownHostException": 14,
    "java.io.IOException": 5,
    "java.io.EOFException": 104,
    "org.apache.http.conn.ConnectTimeoutException": 110,
    "org.apache.commons.net.MalformedServerReplyException": 71,
    "org.apache.http.NoHttpResponseException": 32,
    "java.io.InterruptedIOException": 32,
}


def _exc_to_net(param1):
    """ translate http code to net code """
    if len(param1) <= 3:
        return 0

    exc = param1.split(' ')[-1]
    if exc in KNOWN_EXC.keys():
        return KNOWN_EXC[exc]
    else:
        logger.warning(
            "Not known Java exception, consider adding it to dictionary: %s",
            param1)
        return 1


def _exc_to_http(param1):
    """ translate exception str to http code"""
    if len(param1) <= 3:
        return int(param1)

    exc = param1.split(' ')[-1]
    if exc in KNOWN_EXC.keys():
        return 0
    else:
        return 500


exc_to_net = np.vectorize(_exc_to_net)
exc_to_http = np.vectorize(_exc_to_http)

# phout_columns = [
#     'send_ts', 'tag', 'interval_real', 'connect_time', 'send_time', 'latency',
#     'receive_time', 'interval_event', 'size_out', 'size_in', 'net_code',
#     'proto_code'
# ]

jtl_columns = [
    'receive_ts', 'interval_real', 'tag', 'retcode', 'success', 'size_in',
    'grpThreads', 'allThreads', 'latency', 'connect_time'
]
jtl_types = {
    'receive_ts': np.int64,
    'interval_real': np.int32,
    'tag': np.str,
    'retcode': np.str,
    'success': np.bool,
    'size_in': np.int32,
    'grpThreads': np.int32,
    'allThreads': np.int32,
    'latency': np.int32,
    'connect_time': np.int32
}


# timeStamp,elapsed,label,responseCode,success,bytes,grpThreads,allThreads,Latency
def string_to_df(data):
    chunk = pd.read_csv(
        StringIO(data),
        sep='\t',
        names=jtl_columns,
        dtype=jtl_types)
    chunk["receive_ts"] = chunk["receive_ts"] / 1000.0
    chunk['receive_sec'] = chunk["receive_ts"].astype(int)
    chunk['interval_real'] = chunk["interval_real"] * 1000
    chunk.set_index(['receive_sec'], inplace=True)
    l = len(chunk)
    chunk['send_time'] = np.zeros(l)
    chunk['receive_time'] = np.zeros(l)
    chunk['interval_event'] = np.zeros(l)
    chunk['size_out'] = np.zeros(l)
    chunk['net_code'] = exc_to_net(chunk['retcode'])
    chunk['proto_code'] = exc_to_http(chunk['retcode'])
    return chunk


class JMeterStatAggregator(object):
    def __init__(self, source):
        self.worker = agg.Worker({"allThreads": ["mean"]}, False)
        self.source = source

    def __iter__(self):
        for ts, chunk in self.source:
            stats = self.worker.aggregate(chunk)
            yield [{'ts': ts,
                    'metrics': {'instances': stats['allThreads']['mean'],
                                'reqps': 0}}]

    def close(self):
        pass


class JMeterReader(object):
    def __init__(self, filename):
        self.buffer = ""
        self.stat_buffer = ""
        self.jtl = open(filename, 'r')
        self.closed = False
        self.stat_queue = q.Queue()
        self.stats_reader = JMeterStatAggregator(TimeChopper(
            self.__read_stat_queue(), 3))

    def __read_stat_queue(self):
        while not self.closed:
            for _ in range(self.stat_queue.qsize()):
                try:
                    si = self.stat_queue.get_nowait()
                    if si is not None:
                        yield si
                except q.Empty:
                    break

    def next(self):
        if self.closed:
            raise StopIteration
        data = self.jtl.read(1024 * 1024 * 10)
        if data:
            parts = data.rsplit('\n', 1)
            if len(parts) > 1:
                ready_chunk = self.buffer + parts[0] + '\n'
                self.buffer = parts[1]
                df = string_to_df(ready_chunk)
                self.stat_queue.put(df)
                return df
            else:
                self.buffer += parts[0]
        else:
            self.jtl.readline()
        return None

    def __iter__(self):
        return self

    def close(self):
        self.closed = True
        self.jtl.close()
