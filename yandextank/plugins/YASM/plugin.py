import ctypes
import re

import time
from Queue import Empty

from multiprocessing import Queue, Event, Process

import logging
from yandextank.common.interfaces import MonitoringPlugin
from yasmapi import RtGolovanRequest
from threading import Thread, _active

logger = logging.getLogger(__name__)

DEFAULT_SIGNALS = [
    'portoinst-cpu_usage_cores_tmmv',
    'portoinst-cpu_guarantee_cores_tmmv',
    'portoinst-cpu_limit_cores_tmmv',
    'portoinst-cpu_wait_cores_tmmv',
    'portoinst-memory_usage_gb_tmmv',
    'portoinst-memory_limit_gb_tmmv',
    'portoinst-io_read_fs_bytes_tmmv',
    'portoinst-io_write_fs_bytes_tmmv',
    'portoinst-io_limit_bytes_tmmv',
    'conv(unistat-auto_disk_rootfs_usage_bytes_axxx, Gi)',
    'conv(unistat-auto_disk_rootfs_total_bytes_axxx, Gi)',
    'portoinst-net_mb_summ',
    'portoinst-net_guarantee_mb_summ',
    'portoinst-net_limit_mb_summ'
]


def signals_stream(hosts, tags, signals):
    for point in RtGolovanRequest({host: {tags: signals} for host in hosts}):
        # logger.info('YASM data:\n{}'.format(point.values))
        yield point.ts, {host: point.values[host][tags] for host in hosts}


def map_metric_name(name):
    NAME_MAP = {r'conv\(.+\)': r'(?<=conv\().+?(?=,)'}
    for pattern, mask in NAME_MAP.items():
        if re.match(pattern, name):
            name = re.findall(mask, name)[0]
            break
    return 'custom:{}'.format(name)


def convert_value(name, value):
    return value


def ctype_async_raise(thread_obj, exception):
    found = False
    target_tid = 0
    for tid, tobj in _active.items():
        if tobj is thread_obj:
            found = True
            target_tid = tid
            break

    if not found:
        raise ValueError("Invalid thread object")

    ret = ctypes.pythonapi.PyThreadState_SetAsyncExc(target_tid, ctypes.py_object(exception))
    # ref: http://docs.python.org/c-api/init.html#PyThreadState_SetAsyncExc
    if ret == 0:
        raise ValueError("Invalid thread ID")
    elif ret > 1:
        # Huh? Why would we notify more than one threads?
        # Because we punch a hole into C level interpreter.
        # So it is better to clean up the mess.
        ctypes.pythonapi.PyThreadState_SetAsyncExc(target_tid, 0)
        raise SystemError("PyThreadState_SetAsyncExc failed")
    logger.debug("Successfully set asynchronized exception for %s", target_tid)


def monitoring_data(ts, data, comment=''):
    return {
        "timestamp": ts,
        "data": {
            host: {
                "comment": comment,
                "metrics": {map_metric_name(name): convert_value(name, value) for name, value in host_data.items()}
            }
            for host, host_data in data.items()}}


class ImmutableDict(dict):
    def __init__(self, _dict):
        super(ImmutableDict, self).__init__(_dict)

    def __setitem__(self, key, value):
        raise ValueError('Immutable dict')

    def set_copy(self, key=None, value=None):
        copy = dict(self)
        if key is None:
            return copy
        else:
            copy[key] = value
            return copy


class Plugin(MonitoringPlugin):
    RECEIVE_TIMEOUT = 30

    def __init__(self, core, cfg, cfg_updater=None):
        super(Plugin, self).__init__(core, cfg)
        self.data_queue = Queue()
        self.start_event = Event()
        self.stop_event = Event()
        self.last_ts = 0
        self.data_buffer = []

    def add_listener(self, plugin):
        self.listeners.append(plugin)

    def send_collected_data(self, data):
        """sends pending data set to listeners"""
        for listener in self.listeners:
            listener.monitoring_data(data)

    def is_test_finished(self):
        if len(self.data_buffer) > 0:
            data, self.data_buffer = self.data_buffer, []
            self.send_collected_data(data)
            logger.info('YASM data transmitted')
        return -1

    def prepare_test(self):
        self.yasm_receiver_ps = Process(target=self.yasm_receiver,
                                        args=(self.get_option('hosts'),
                                              self.get_option('tags'),
                                              self.get_option('signals'),
                                              ))
        self.yasm_receiver_ps.start()
        self.consumer_thread = Thread(target=self.consumer)
        self.consumer_thread.start()

    def start_test(self):
        self.start_event.set()
        logger.info('Listeners: {}'.format(self.listeners))

    def end_test(self, retcode):
        self.end_time = time.time()
        while self.last_ts < self.end_time and not self.stop_event.is_set():
            try:
                logger.info('Waiting for yasm metrics')
                time.sleep(1)
            except KeyboardInterrupt:
                logger.info('Metrics receiving interrupted')
                break
        self.stop_event.set()
        self.consumer_thread.join()
        self.yasm_receiver_ps.join()
        self.send_rest()
        return retcode

    def send_rest(self):
        if len(self.data_buffer) > 0:
            data, self.data_buffer = self.data_buffer, []
            self.send_collected_data(data)

    def consumer(self):
        while not self.stop_event.is_set():
            try:
                data = self.data_queue.get(timeout=self.RECEIVE_TIMEOUT)
                self.data_buffer.append(ImmutableDict(data))
            except Empty:
                logger.warning(
                    'Not receiving any data from YASM. Probably your hosts/tags specification is not correct')
                self.stop_event.set()
                if self.yasm_receiver_ps.is_alive():
                    self.yasm_receiver_ps.terminate()
                break

    def yasm_receiver(self, hosts, tags, custom_signals=None,
                      include_default_signals=True):
        if custom_signals is None:
            signals = DEFAULT_SIGNALS
        else:
            signals = DEFAULT_SIGNALS + custom_signals
        stream = signals_stream(hosts, tags, signals)
        try:
            while not self.stop_event.is_set():
                ts, data = stream.next()
                logger.info('Received monitoring data for {}'.format(ts))
                self.last_ts = int(ts)
                chunk = monitoring_data(ts, data)
                if self.start_event.is_set():
                    self.data_queue.put(chunk)
        finally:
            logger.info('Closing YASM receiver thread')
            # logger.info('Putting to monitoring data queue: {}'.format(chunk))

            # host='QLOUD'
            # tags='itype=qloud;prj=load.lpq.lpq-prod'
            # signals =
