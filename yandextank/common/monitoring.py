import logging
import time
import typing
from yandextank.common.interfaces import MonitoringCollectorProtocol, MonitoringChunk
from yandextank.common.util import observetime
from re import match, findall
from threading import Thread, Event, Lock
from queue import Queue

Metric = dict[str, typing.Any]
Buffer = dict[float, dict[str, typing.Any]]
Composer = typing.Callable[[Metric, Buffer], None]

LOGGER = logging.getLogger(__name__)


def convert_name(name: str):
    NAME_MAP = {r'conv\(.+\)': r'(?<=conv\().+?(?=,)'}
    for pattern, mask in NAME_MAP.items():
        if match(pattern, name):
            name = findall(mask, name)[0]
            break
    return 'custom:{}'.format(name)[:100]


def monitoring_data(pname, metrics, comment=''):
    try:
        return {
            'timestamp': tuple(metrics)[0],
            'data': {
                pname: {
                    'comment': comment,
                    'metrics': {convert_name(name): value for name, value in tuple(metrics.values())[0].items()},
                }
            },
        }
    except (IndexError, ValueError) as ve:
        LOGGER.warning("Can't format. Wrong data %s. %s", metrics, ve, exc_info=True)


class MonitoringPanel(object):

    '''
    The class Panel is used for initializing and managing structural levels for collecting monitoring data passed through the configuration file.
    '''

    def __init__(self, name, timeout, queue: Queue):
        self.name = name
        self.queue = queue
        self.timeout = timeout
        self.sensors = set()
        self.buffer: Buffer = dict()

    def add_sensors(self, sensors):
        self.sensors.union(sensors)

    @observetime('MonitoringPanel.process_queue', LOGGER)
    def process_queue(self):
        try:
            while not self.queue.empty():
                data = self.queue.get()
                metrics = []
                if isinstance(data, dict) and 'timestamp' in data:
                    metrics = [data]
                elif isinstance(data, list):
                    metrics = list(filter(lambda d: isinstance(d, typing.Mapping), data))
                for m in metrics:
                    ts = m['timestamp']
                    if ts in self.buffer:
                        self.buffer[ts].update({m['sensor']: m['value']})
                    else:
                        self.buffer[ts] = {m['sensor']: m['value']}
        except KeyError as error:
            LOGGER.warning('Got data in invalid format %s', error)
        except (IOError, OSError) as error:
            LOGGER.warning('Panel %s processing queue error. %s', self.name, error, exc_info=True)

    def get_metrics(self):
        now = time.time()
        outbuffer = list()
        complete_ts = list()
        for ts, metrics in self.buffer.items():
            if self.sensors.issubset(set(metrics.keys())) or (now - ts) > self.timeout:
                outbuffer.append({ts: metrics})
                complete_ts.append(ts)
        for ts in complete_ts:
            self.buffer.pop(ts)
        return outbuffer


class MonitoringSensorProtocol(typing.Protocol):
    def fetch_metrics(self):
        ...


class DefaultCollector(MonitoringCollectorProtocol):
    def __init__(self, *, logger: logging.Logger, timeout: float, poll_interval: float):
        self.logger = logger
        self.stop_event = Event()
        self.delivery_interval = timeout
        self.poll_interval = poll_interval
        self.sensors: list[Thread] = []
        self.panels: list[Thread] = []
        self._data_buffer = []
        self._buffer_lock = Lock()

    def add_panel(self, panel: MonitoringPanel):
        self.panels.append(Thread(target=self.run_panel, args=(panel,)))

    def add_sensor(self, sensor: MonitoringSensorProtocol):
        self.sensors.append(Thread(target=self.run_sensor, args=(sensor,)))

    def start(self):
        self.logger.debug('Starting %s panels', len(self.panels))
        for thread in self.panels:
            if not thread.is_alive():
                thread.start()
        self.logger.debug('Starting %s sensors', len(self.sensors))
        for thread in self.sensors:
            if not thread.is_alive():
                thread.start()

    def stop(self):
        self.logger.info('Stopping Monitoring Collector in %s seconds', self.poll_interval)
        time.sleep(self.poll_interval + 1)
        self.stop_event.set()
        for thread in self.sensors:
            if thread.is_alive():
                thread.join()
        for thread in self.panels:
            if thread.is_alive():
                thread.join()

    def poll(self) -> MonitoringChunk:
        with self._buffer_lock:
            data, self._data_buffer = self._data_buffer, []
        return data

    def run_sensor(self, sensor: MonitoringSensorProtocol):
        while not self.stop_event.wait(self.poll_interval):
            sensor.fetch_metrics()

    def run_panel(self, panel: MonitoringPanel):
        try:
            while not self.stop_event.wait(self.poll_interval):
                panel.process_queue()
                with self._buffer_lock:
                    for metric in panel.get_metrics():
                        self._data_buffer.append(monitoring_data(panel.name, metric))
        except Exception as ex:
            self.logger.exception('Error %s for monitoring panel %s.', type(ex), panel.name)
        finally:
            self.logger.info('Monitoring panel %s will be closed after %s second', panel.name, self.delivery_interval)
            time.sleep(self.delivery_interval)
            panel.process_queue()
            with self._buffer_lock:
                for ts, metrics in panel.buffer.items():
                    self._data_buffer.append(monitoring_data(panel.name, {ts: metrics}))
