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


def signals_stream(panel):
    '''
    :type yasmapi_cfg: Panel
    :return: Panel, float, dict
    '''
    for point in RtGolovanRequest(panel.as_dict):
        logger.debug('received YASM data for {} for following hosts an tags: {}'.
                     format(point.ts,
                            {host: tags.keys() for host, tags in point.values.items()}))
        yield point.ts, point.values[panel.host][panel.tags]


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
        self.panels = [Panel(alias, **attrs) for alias, attrs in panels.items()]
        self._as_dict = None

    @property
    def as_dict(self):
        if self._as_dict is None:
            yasmapi_cfg = {}
            for panel in self.panels:
                yasmapi_cfg.setdefault(panel.host, {})[panel.tags] = panel.signals
            logger.info('yasmapi cfg: {}'.format(yasmapi_cfg))
            self._as_dict = yasmapi_cfg
        return self._as_dict


class Panel(object):
    def __init__(self, alias, host, tags, signals=None, default_signals=True):
        self.queue = Queue()
        self.alias = alias
        custom_signals = signals if signals else []
        self.signals = DEFAULT_SIGNALS + custom_signals if default_signals else custom_signals
        self.host = host
        self.tags = tags.strip(';')
        if len(self.signals) == 0:
            logger.warning('No signals specified for {} panel'.format(self.alias))
        self.as_dict = {self.host: {self.tags: self.signals}}
        self.last_ts = 0
        self.stop_trigger = Event()

    def stop(self):
        self.stop_trigger.set()


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


class YasmMPReceiver(object):
    def __init__(self, yasm_cfg, yasmapi_timeout):
        """

        :type data_queue: Queue
        :type yasm_cfg: YasmCfg
        """
        self.panels = yasm_cfg.panels
        self.data_queue = Queue()
        self.timeout = yasmapi_timeout
        self._data_buffer = []
        self._start_event = Event()
        self._stop_event = Event()
        self.ps_pool = {panel.alias: Process(target=self.single_receiver,
                                             args=(panel,))
                        for panel in self.panels}
        self.consumers = {panel.alias: Thread(target=self.single_controller, args=(panel, self.ps_pool[panel.alias]))
                          for panel in self.panels}

    def get_buffered_data(self):
        data, self._data_buffer = self._data_buffer, []
        return data

    def start_collecting(self):
        [p.start() for p in self.ps_pool.values()]

    def start_transmitting(self):
        self._start_event.set()
        [consumer.start() for consumer in self.consumers.values()]

    def single_receiver(self, panel):
        # ignore SIGINT (process is controlled by .stop_event)
        """

        :type panel: Panel
        """
        signal.signal(signal.SIGINT, signal.SIG_IGN)

        stream = signals_stream(panel)
        try:
            while not panel.stop_trigger.is_set():
                ts, data = stream.next()
                if self._start_event.is_set():
                    panel.queue.put((ts, {panel.alias: data}))
        finally:
            logger.info('Closing panel {} receiver thread'.format(panel.alias))

    def single_controller(self, panel, ps):
        """

        :type ps: Process
        :type panel: Panel
        """
        while not panel.stop_trigger.is_set():
            try:
                ts, data = panel.queue.get(timeout=self.timeout)
                panel.last_ts = ts
                # logger.info('Received monitoring data for {}'.format(ts))
                self._data_buffer.append(monitoring_data(ts, data))
            except Empty:
                logger.warning(
                    'Not receiving any data from YASM. Probably your hosts/tags specification is not correct')
                panel.stop_trigger.set()
                if ps.is_alive():
                    ps.terminate()
                break
            except KeyboardInterrupt:
                logging.warning('Interrupting collecting metrics for panel {}'.format(panel.alias))
                panel.stop_trigger.set()
                if ps.is_alive():
                    ps.terminate()
                break

    def stop_now(self):
        end_time = time.time()
        active_panels = self.panels
        while len(active_panels) > 0:
            try:
                for panel in active_panels:
                    if panel.last_ts < end_time and not self._stop_event.is_set():
                        logger.info('Waiting for yasm metrics for panel {}'.format(panel.alias))
                    else:
                        panel.stop_trigger.set()
                        self.ps_pool[panel.alias].join()
                        self.consumers[panel.alias].join()
                active_panels = [panel for panel in active_panels if not panel.stop_trigger.is_set()]
                if len(active_panels) > 0:
                    time.sleep(5)
            except KeyboardInterrupt:
                logger.info('Metrics receiving interrupted')
                [panel.stop_trigger.set() for panel in active_panels]
                [(self.ps_pool[panel.alias].join(), self.consumers[panel.alias].join()) for panel in active_panels]


class Plugin(MonitoringPlugin):
    def __init__(self, core, cfg, cfg_updater=None):
        super(Plugin, self).__init__(core, cfg)
        self.start_event = Event()
        self.stop_event = Event()
        self.last_ts = 0
        if self.get_option('verbose_logging'):
            logger.setLevel(logging.DEBUG)
        self.yasm_receiver = YasmMPReceiver(YasmCfg(self.get_option('panels')),
                                            self.get_option('timeout'))

    def add_listener(self, plugin):
        self.listeners.append(plugin)

    def send_collected_data(self, data):
        """sends pending data set to listeners"""
        for listener in self.listeners:
            listener.monitoring_data(data)

    def is_test_finished(self):
        data = self.yasm_receiver.get_buffered_data()
        if len(data) > 0:
            self.send_collected_data(data)
        return -1

    def prepare_test(self):
        self.yasm_receiver.start_collecting()

    def start_test(self):
        self.yasm_receiver.start_transmitting()
        logger.info('Listeners: {}'.format(self.listeners))

    def end_test(self, retcode):
        self.yasm_receiver.stop_now()
        self.send_rest()
        return retcode

    def send_rest(self):
        data = self.yasm_receiver.get_buffered_data()
        if len(data) > 0:
            self.send_collected_data(data)
