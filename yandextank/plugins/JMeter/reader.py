# -*- coding: UTF-8 -*-
import pandas as pd
import numpy as np
import queue as q
import logging
from StringIO import StringIO

from ..Aggregator import aggregator as agg
from ..Aggregator.chopper import TimeChopper

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
    "java.net.URISyntaxException": 22,
    "java.io.FileNotFoundException": 2,
    "java.io.IOException": 5,
    "java.io.EOFException": 104,
    "org.apache.http.conn.ConnectTimeoutException": 110,
    "org.apache.commons.net.MalformedServerReplyException": 71,
    "org.apache.http.NoHttpResponseException": 32,
    "java.io.InterruptedIOException": 32,
    "javax.net.ssl.SSLHandshakeException": 5,
}


def _exc_to_net(param1, success):
    """ translate http code to net code. if accertion failed, set net code to 314 """
    if len(param1) <= 3:
        # FIXME: we're unable to use better logic here, because we should support non-http codes
        # but, we should look for core.util.HTTP or some other common logic
        # here
        if success:
            return 0
        else:
            return 314

    exc = param1.split(' ')[-1]
    if exc in KNOWN_EXC.keys():
        return KNOWN_EXC[exc]
    else:
        logger.warning(
            "Unknown Java exception, consider adding it to dictionary: %s",
            param1)
        return 41


def _exc_to_http(param1):
    """ translate exception str to http code"""
    if len(param1) <= 3:
        try:
            int(param1)
        except:
            logger.error(
                "JMeter wrote some strange data into codes column: %s", param1)
        else:
            return int(param1)

    exc = param1.split(' ')[-1]
    if exc in KNOWN_EXC.keys():
        return 0
    else:
        logger.warning("Unknown Java exception. %s", param1)
        return 0


exc_to_net = np.vectorize(_exc_to_net)
exc_to_http = np.vectorize(_exc_to_http)

# phout_columns = [
#     'send_ts', 'tag', 'interval_real', 'connect_time', 'send_time', 'latency',
#     'receive_time', 'interval_event', 'size_out', 'size_in', 'net_code',
#     'proto_code'
# ]

jtl_columns = [
    'send_ts', 'interval_real', 'tag', 'retcode', 'success', 'size_in',
    'grpThreads', 'allThreads', 'latency', 'connect_time'
]
jtl_types = {
    'send_ts': np.int64,
    'interval_real': np.int64,
    'tag': np.str,
    'retcode': np.str,
    'success': np.bool,
    'size_in': np.int64,
    'grpThreads': np.int64,
    'allThreads': np.int64,
    'latency': np.int64,
    'connect_time': np.float64,
}


def fix_latency(row):
    if row['latency'] < row['connect_time']:
        if row['interval_real'] < row['connect_time']:
            latency = 0
        else:
            latency = row['interval_real'] - row['connect_time']
    else:
        latency = row['latency'] - row['connect_time']
    return latency


# timeStamp,elapsed,label,responseCode,success,bytes,grpThreads,allThreads,Latency
def string_to_df(data):
    chunk = pd.read_csv(
        StringIO(data), sep='\t', names=jtl_columns, dtype=jtl_types)
    chunk["receive_ts"] = (chunk["send_ts"] + chunk['interval_real']) / 1000.0
    chunk['receive_sec'] = chunk["receive_ts"].astype(np.int64)
    chunk['interval_real'] = chunk["interval_real"] * 1000  # convert to µs
    chunk.set_index(['receive_sec'], inplace=True)
    l = len(chunk)
    chunk['connect_time'] = (chunk['connect_time'].fillna(0) *
                             1000).astype(np.int64)
    chunk['latency'] = chunk['latency'] * 1000
    chunk['latency'] = chunk.apply(fix_latency, axis=1)
    chunk['send_time'] = np.zeros(l)
    chunk['receive_time'] = chunk['interval_real'] - \
        chunk['latency'] - chunk['connect_time']
    chunk['interval_event'] = np.zeros(l)
    chunk['size_out'] = np.zeros(l)
    chunk['net_code'] = exc_to_net(chunk['retcode'], chunk['success'])
    chunk['proto_code'] = exc_to_http(chunk['retcode'])
    return chunk


class JMeterStatAggregator(object):
    def __init__(self, source):
        self.worker = agg.Worker({"allThreads": ["mean"]}, False)
        self.source = source

    def __iter__(self):
        for ts, chunk in self.source:
            stats = self.worker.aggregate(chunk)
            yield [{
                'ts': ts,
                'metrics': {
                    'instances': stats['allThreads']['mean'],
                    'reqps': 0
                }
            }]

    def close(self):
        pass


class JMeterReader(object):
    def __init__(self, filename):
        self.buffer = ""
        self.stat_buffer = ""
        self.jtl_file = filename
        self.jmeter_finished = False
        self.agg_finished = False
        self.closed = False
        self.stat_queue = q.Queue()
        self.stats_reader = JMeterStatAggregator(
            TimeChopper(self._read_stat_queue(), 3))

    def _read_stat_queue(self):
        while not self.closed:
            for _ in range(self.stat_queue.qsize()):
                try:
                    si = self.stat_queue.get_nowait()
                    if si is not None:
                        yield si
                except q.Empty:
                    break

    def _read_jtl_chunk(self, jtl):
        data = jtl.read(1024 * 1024 * 10)
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
            if self.jmeter_finished:
                self.agg_finished = True
            jtl.readline()
        return None

    def __iter__(self):
        with open(self.jtl_file, 'r') as jtl:
            while not self.closed:
                yield self._read_jtl_chunk(jtl)
            yield self._read_jtl_chunk(jtl)

    def close(self):
        self.closed = True
