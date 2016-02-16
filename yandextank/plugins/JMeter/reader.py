import os
import json
import pandas as pd
from StringIO import StringIO
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


def exc_to_net(param1):
    """ translate http code to net code """
    if len(param1) <= 3:
        return '1'

    exc = param1.split(' ')[-1]
    if exc in KNOWN_EXC.keys():
        return KNOWN_EXC[exc]
    else:
        logger.warning(
            "Not known Java exception, consider adding it to dictionary: %s",
            param1)
        return '1'


def exc_to_http(param1):
    """ translate exception str to http code"""
    if len(param1) <= 3:
        return param1

    exc = param1.split(' ')[-1]
    if exc in KNOWN_EXC.keys():
        return '0'
    else:
        return '500'


jtl_columns = [
    'send_ts', 'tag', 'interval_real', 'connect_time', 'send_time', 'latency',
    'receive_time', 'interval_event', 'size_out', 'size_in', 'net_code',
    'proto_code'
]

jtl_columns = [
    'send_ts', 'interval_real', 'tag', 'proto_code', 'success', 'size_in',
    'grpThreads', 'allThreads', 'Latency'
]


# timeStamp,elapsed,label,responseCode,success,bytes,grpThreads,allThreads,Latency
def string_to_df(data):
    chunk = pd.read_csv(StringIO(data), sep='\t', names=phout_columns)
    chunk['receive_ts'] = chunk.send_ts + chunk.interval_real / 1e6
    chunk['receive_sec'] = chunk.receive_ts.astype(int)
    # TODO: consider configuration for the following:
    chunk['tag'] = chunk.tag.str.rsplit('#', 1, expand=True)[0]
    chunk.set_index(['receive_sec'], inplace=True)
    return chunk


class JMeterReader(object):
    def __init__(self, filename):
        self.buffer = ""
        self.stat_buffer = ""
        self.jtl = open(filename, 'r')
        self.closed = False

    def next(self):
        if self.closed:
            raise StopIteration
        data = self.jtl.read(1024 * 1024 * 10)
        if data:
            parts = data.rsplit('\n', 1)
            if len(parts) > 1:
                ready_chunk = self.buffer + parts[0] + '\n'
                self.buffer = parts[1]
                return string_to_df(ready_chunk)
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


class JMeterReader1(object):
    """ JTL files reader """

    def __init__(self, owner, jmeter):
        self.jmeter = jmeter
        self.results = None
        self.partial_buffer = ''
        self.buffer_size = 3

    def check_open_files(self):
        if not self.results and os.path.exists(self.jmeter.jtl_file):
            logger.debug("Opening jmeter out file: %s", self.jmeter.jtl_file)
            self.results = open(self.jmeter.jtl_file, 'r')

    def close_files(self):
        if self.results:
            self.results.close()

    def get_next_sample(self, force):
        if self.results:
            read_lines = self.results.readlines(2 * 1024 * 1024)
            logger.debug("About to process %s result lines", len(read_lines))
            for line in read_lines:
                if not line:
                    return None
                    # timeStamp,elapsed,label,responseCode,success,bytes,grpThreads,allThreads,Latency
                if self.partial_buffer != '':
                    line = self.partial_buffer + line
                    self.partial_buffer = ''
                data = line.rstrip().split("\t")
                if line[-1] != '\n' or len(data) < 9:
                    self.partial_buffer = line
                    # logger.warning("Wrong jtl line, skipped: %s", line)
                    continue
                cur_time = int(data[0]) / 1000
                netcode = '0' if data[4] == 'true' else exc_to_net(data[3])

                if not cur_time in self.data_buffer.keys():
                    if self.data_queue and self.data_queue[0] >= cur_time:
                        logger.warning(
                            "Aggregator data dates must be sequential: %s vs %s"
                            % (cur_time, self.data_queue[0]))
                        cur_time = self.data_queue[0]  # 0 or -1?
                    else:
                        self.data_queue.append(cur_time)
                        self.data_buffer[cur_time] = []

                connect_value = 0
                if self.jmeter.connect_time:
                    connect_value = int(data[9])

                # marker, threads, overallRT, httpCode, netCode
                data_item = [
                    data[2], int(data[7]), int(data[1]),
                    self.exc_to_http(data[3]), netcode
                ]
                # bytes:     sent    received
                data_item += [0, int(data[5])]
                # connect    send    latency    receive
                data_item += [connect_value, 0, int(data[8]),
                              int(data[1]) - int(data[8])]
                # accuracy
                data_item += [0]
                self.data_buffer[cur_time].append(data_item)

        if not force and self.data_queue and (
                self.data_queue[-1] - self.data_queue[0]) > self.buffer_size:
            return self.pop_second()
        elif force and self.data_queue:
            return self.pop_second()
        else:
            return None
