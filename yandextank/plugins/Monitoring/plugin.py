import copy
import re

import time
from Queue import Empty

from multiprocessing import Queue, Event

import logging
from yandextank.common.interfaces import AbstractPlugin
from yasmapi import RtGolovanRequest
from threading import Thread

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


def signals_stream(host, tags, signals):
    for point in RtGolovanRequest({host: {tags: signals}}):
        yield point.ts, point.values[host][tags]


def map_metric_name(name):
    NAME_MAP = {r'conv\(.+\)': r'(?<=conv\().+?(?=,)'}
    for pattern, mask in NAME_MAP.items():
        if re.match(pattern, name):
            name = re.findall(mask, name)[0]
            break
    return 'custom:{}'.format(name)


def convert_value(name, value):
    return value


def monitoring_data(ts, signals, comment=''):
    return {
        "timestamp": ts,
        "data": {
            "hostname": {
                "comment": comment,
                "metrics": {map_metric_name(name): convert_value(name, value) for name, value in signals.items()}
            }
        }}


class Plugin(AbstractPlugin):
    def __init__(self, core, cfg, cfg_updater=None):
        super(Plugin, self).__init__(core, cfg, cfg_updater=None)
        self.listeners = []
        self.data_queue = Queue()
        self.start_event = Event()
        self.stop_event = Event()

    def add_listener(self, plugin):
        self.listeners.append(plugin)

    def send_collected_data(self, data):
        """sends pending data set to listeners"""
        # data = self.__collected_data
        # self.__collected_data = []
        for listener in self.listeners:
            # deep copy to ensure each listener gets it's own copy
            listener.monitoring_data([copy.deepcopy(data)])

    def is_test_finished(self):
        if not self.data_queue.empty():
            data = self.data_queue.get_nowait()
            self.send_collected_data(data)
            logger.info('Monitoring data transmitted')
        return -1

    def prepare_test(self):
        self.yasm_client_thread = Thread(target=self.monitoring_to_queue,
                                         args=(self.get_option('host'),
                                               self.get_option('tags'),
                                               self.get_option('signals'),
                                               ))
        self.yasm_client_thread.start()

    def start_test(self):
        self.start_event.set()
        logger.info('Listeners: {}'.format(self.listeners))

    def end_test(self, retcode):
        self.stop_event.set()
        self.send_rest()
        self.yasm_client_thread.join()

    def send_rest(self):
        while not self.data_queue.empty():
            self.send_collected_data(self.data_queue.get_nowait())

    def monitoring_to_queue(self, host, tags, custom_signals=None,
                            include_default_signals=True):
        if custom_signals is None:
            signals = DEFAULT_SIGNALS
        else:
            signals = DEFAULT_SIGNALS + custom_signals
        stream = signals_stream(host, tags, signals)
        while not self.stop_event.is_set():
            ts, data = stream.next()
            logger.info('Received monitoring data for {}'.format(ts))
            chunk = monitoring_data(ts, data)
            if self.start_event.is_set():
                self.data_queue.put(chunk)
                logger.info('Putting to monitoring data queue: {}'.format(chunk))
            time.sleep(4.5)

            # host='QLOUD'
            # tags='itype=qloud;prj=load.lpq.lpq-prod'
            # signals =
