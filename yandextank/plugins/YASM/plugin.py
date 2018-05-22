import re

import time
from Queue import Empty

from multiprocessing import Queue, Event, Process

import logging

import signal
from yandextank.common.interfaces import MonitoringPlugin
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


def signals_stream(yasmapi_cfg):
    '''
    :type yasmapi_cfg: YasmCfg
    :return:
    '''
    for point in RtGolovanRequest(yasmapi_cfg.as_dict()):
        # logger.info('YASM data:\n{}'.format(point.values))
        yield point.ts, {panel.alias: point.values[panel.host][panel.tags] for panel in yasmapi_cfg.panels}


def map_metric_name(name):
    NAME_MAP = {r'conv\(.+\)': r'(?<=conv\().+?(?=,)'}
    for pattern, mask in NAME_MAP.items():
        if re.match(pattern, name):
            name = re.findall(mask, name)[0]
            break
    return 'custom:{}'.format(name)


def convert_value(name, value):
    return value


def monitoring_data(ts, data, comment=''):
    return ImmutableDict({
        "timestamp": ts,
        "data": {
            host: {
                "comment": comment,
                "metrics": {map_metric_name(name): convert_value(name, value) for name, value in host_data.items()}
            }
            for host, host_data in data.items()}})


class YasmCfg(object):

    def __init__(self, panels):
        self.panels = [self.Panel(alias, **attrs) for alias, attrs in panels.items()]

    def as_dict(self):
        yasmapi_cfg =  {}#{panel.host: {panel.tags: panel.signals} for panel in self.panels}
        for panel in self.panels:
            yasmapi_cfg.setdefault(panel.host, {})[panel.tags] = panel.signals
        logger.info('yasmapi cfg: {}'.format(yasmapi_cfg))
        return yasmapi_cfg

    class Panel(object):
        def __init__(self, alias, host, tags, signals=None, default_signals=True):
            self.alias = alias
            custom_signals = signals if signals else []
            self.signals = DEFAULT_SIGNALS + custom_signals if default_signals else custom_signals
            self.host = host
            self.tags = tags
            if len(self.signals) == 0:
                logger.warning('No signals specified for {} panel'.format(self.alias))
            self.dict_cfg = {self.host: {self.tags: self.signals}}


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
    RECEIVE_TIMEOUT = 45

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
        return -1

    def prepare_test(self):
        yasmapi_cfg = YasmCfg(self.get_option('panels'))
        self.yasm_receiver_ps = Process(target=self.yasm_receiver, args=(yasmapi_cfg,),)
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
                logger.info('Waiting for yasm metrics till {}'.format(self.end_time))
                time.sleep(5)
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
                ts, data = self.data_queue.get(timeout=self.RECEIVE_TIMEOUT)
                # logger.info('Received monitoring data for {}'.format(ts))
                self.last_ts = ts
                self.data_buffer.append(monitoring_data(ts, data))
            except Empty:
                logger.warning(
                    'Not receiving any data from YASM. Probably your hosts/tags specification is not correct')
                self.stop_event.set()
                if self.yasm_receiver_ps.is_alive():
                    self.yasm_receiver_ps.terminate()
                break

    def yasm_receiver(self, yasmapi_cfg):
        # ignore SIGINT (process is controlled by .stop_event)
        signal.signal(signal.SIGINT, signal.SIG_IGN)

        stream = signals_stream(yasmapi_cfg)
        try:
            while not self.stop_event.is_set():
                ts, data = stream.next()
                if self.start_event.is_set():
                    self.data_queue.put((ts, data))
        finally:
            logger.info('Closing YASM receiver thread')
