import logging
import uuid
import time
import os
import getpass
import six
from yandextank.contrib.netort.netort.data_manager.common.util import thread_safe_property
from typing import Callable, Dict, Optional, Set, Any

from .metrics import Metric, Event
from .clients import available_clients
from .router import MetricsRouter
from .common.interfaces import AbstractMetric

if six.PY3:
    from queue import Queue
else:  # six.PY2
    # noinspection PyUnresolvedReferences
    from Queue import Queue

logger = logging.getLogger(__name__)


# TODO: move code that works with config to library's clients (e.g., Volta).
# Classes of this library should provide constructors with described arguments only
# noinspection PyBroadException
class DataSession(object):
    """
    Workflow:
        * create DataSession object
        * use `new_metric` to add metrics to your datasession
        * use `metric.put` to add data to the metric
        * call `close` to close your datasession

    Note:
        * send your data in chunks because it could be of bigger size that server's buffer

    Args:
        config(dict): configuration options (list of DataManager clients, test meta data etc)

    TODO:
        * move config parameters to kwargs, describe them here
        * fight performance issues (probably caused by poor pandas write_csv performance)
    """
    def __init__(self, config: Dict, tankapi_info: Dict = None, config_filenames: Set = None, artifacts_dir: str = None, test_start: float = None):
        self.start_ts = time.time()
        self.config = config
        self.operator = self.__get_operator()
        self.job_id = config.get('test_id', 'job_{uuid}'.format(uuid=uuid.uuid4()))
        logger.info('Created new local data session: %s', self.job_id)
        self.tankapi_info = tankapi_info
        self.config_filenames = config_filenames or set()
        self.test_start = test_start if test_start else int(time.time() * 10**6)
        self.artifacts_base_dir = artifacts_dir or './logs'
        self._artifacts_dir: Optional[str] = None
        self.manager = DataManager()

        self.clients = []
        self.__create_clients(config.get('clients', []))
        logger.debug('DataSession clients: %s', self.clients)

    # TODO: extract client creation as factory method
    # TODO: consider removing clients from config and add them via `new_client` method
    def __create_clients(self, clients: Dict):
        for client_meta in clients:
            type_ = client_meta.get('type')
            if not type_:
                raise ValueError('Client type should be defined.')
            if type_ in available_clients:
                client = available_clients[type_](client_meta, self)
                self.subscribe(client.put)
                self.clients.append(client)
            else:
                raise NotImplementedError('Unknown client type: %s' % type_)

    def new_true_metric(self, meta: Dict, raw=True, aggregate=False, parent: str = None, case: str = None) -> AbstractMetric:
        return self.manager.new_true_metric(meta=meta,
                                            test_start=self.test_start,
                                            raw=raw, aggregate=aggregate,
                                            parent=parent, case=case)

    def new_event_metric(self, meta: Dict, raw=True, aggregate=False, parent: str = None, case: str = None) -> AbstractMetric:
        return self.manager.new_event_metric(meta=meta,
                                             test_start=self.test_start,
                                             raw=raw, aggregate=aggregate,
                                             parent=parent, case=case)

    def subscribe(self, callback: Callable) -> Any:
        return self.manager.subscribe(callback)

    def get_metric_by_id(self, id_: str) -> Any:
        return self.manager.get_metric_by_id(id_)

    def update_job(self, meta: Dict) -> Any:
        for client in self.clients:
            try:
                client.update_job(meta)
            except Exception:
                logger.warning('Client %s job update failed', client)
                logger.debug('Client %s job update failed', client, exc_info=True)
            else:
                logger.debug('Client job updated: %s', client)

    def update_metric(self, meta: Dict) -> None:
        for client in self.clients:
            try:
                client.update_metric(meta)
            except Exception:
                logger.warning('Client %s metric update failed', client)
                logger.debug('Client %s metric update failed', client, exc_info=True)
            else:
                logger.debug('Client metric updated: %s', client)

    # TODO: artifacts dir should be inside "local" client. Or does it?
    @thread_safe_property
    def artifacts_dir(self) -> str:
        if not self._artifacts_dir:
            dir_name = "{dir}/{id}".format(dir=self.artifacts_base_dir, id=self.job_id)
            if not os.path.isdir(dir_name):
                os.makedirs(dir_name)
            os.chmod(dir_name, 0o755)
            self._artifacts_dir = os.path.abspath(dir_name)
        return self._artifacts_dir

    def __get_operator(self) -> str:
        try:
            return self.config.get('operator') or getpass.getuser()
        except:  # noqa: E722
            logger.error(
                "Couldn't get username from the OS. Please, set the 'operator' option explicitly in your config "
                "file.")
            raise

    def close(self, test_end: float):
        logger.info('DataSession received close signal.')
        logger.info('Closing DataManager')
        self.manager.close()
        logger.info('Waiting the rest of data from router...')
        self.manager.router.join()
        logger.info('Sending close to DataSession clients...')
        for client in self.clients:
            try:
                client.close(test_end)
            except Exception:
                logger.warning('Client %s failed to close', client, exc_info=True)
            else:
                logger.debug('Client closed: %s', client)
        logger.info('DataSession finished!')
        logger.info('DataSession time: %s', time.time() - self.start_ts)

    def interrupt(self):
        self.manager.interrupt()
        for client in self.clients:
            try:
                client.close()
            except Exception:
                logger.warning('Client %s failed to close', client)
            else:
                logger.debug('Client closed: %s', client)
        logger.info('DataSession finished!')


class DataManager(object):
    """DataManager routes data to subscribers using metrics meta as a filter. When someone calls
    `new_metric`, DataManager will find the subscribers that are interested in this metric (using meta).
    When someone calls `subscribe`, DataManager finds the metrics that this subscriber is interested in.

    MetricsRouter is a facility that DataManager uses for passing incoming data to subscribers.

    Attributes:
        metrics: All registered metrics for DataManager session
        subscribers: All registered subscribers for DataManager session
        callbacks: callbacks for metric ids <-> subscribers' callbacks, used by router
        routing_queue: incoming unrouted metrics data, will be processed by MetricsRouter to subscribers' callbacks
        router (MetricsRouter object): Router thread. Read routing queue, concat incoming messages by metrics.type,
            left join by callback and call callback w/ resulting dataframe
    """
    def __init__(self):
        self.metrics = {}
        self.metrics_meta = {}
        self.subscribers = {}
        self.callbacks = {}
        self.routing_queue = Queue()
        self.router = MetricsRouter(self)
        self.router.start()

    def new_true_metric(self, meta: Dict, test_start: float, raw=True, aggregate=False, parent: str = None, case: str = None) -> AbstractMetric:
        """
        Create and register metric,
        find subscribers for this metric (using meta as filter) and subscribe

        Return:
            metric: one of Metric
        """
        return self._new_metric(Metric, meta, test_start, raw, aggregate, parent=parent, case=case)

    def new_event_metric(self, meta: Dict, test_start: float, raw=True, aggregate=False, parent: str = None, case: str = None) -> AbstractMetric:
        # type: (dict, float, bool, bool, str, str) -> AbstractMetric
        return self._new_metric(Event, meta, test_start, raw, aggregate, parent=parent, case=case)

    def _new_metric(self, dtype, meta: Dict, test_start: float, raw=True, aggregate=False, parent: str = None, case: str = None) -> AbstractMetric:
        metric_obj = dtype(meta=meta,
                           _queue=self.routing_queue,
                           test_start=test_start,
                           raw=raw, aggregate=aggregate,
                           parent=parent, case=case)  # create metric object
        self.metrics_meta = meta  # register metric meta
        self.metrics[metric_obj.local_id] = metric_obj  # register metric object
        for callback in self.callbacks:
            self.callbacks[callback].add(metric_obj.local_id)
        return metric_obj

    def subscribe(self, callback: Callable):
        """
        Create and register metric subscriber,
        subscribe all existing metrics for it

        Args:
            callback (object method): subscriber's callback
        """
        sub_id = "subscriber_{uuid}".format(uuid=uuid.uuid4())
        # register subscriber in manager
        self.subscribers[sub_id] = callback
        self.callbacks[sub_id] = set(iter(self.metrics))

    def get_metric_by_id(self, id_: str) -> Optional[AbstractMetric]:
        return self.metrics.get(id_)

    def close(self):
        self.router.close()

    def interrupt(self):
        self.router.interrupt()
        self.router.join()


# def usage_sample():
#     import time
#     import pandas as pd
#     config = {
#         'clients': [
#             {
#                 'type': 'luna',
#                 'api_address': 'http://hostname.tld',
#                 'user_agent': 'Tank Test',
#             },
#             {
#                 'type': 'local_storage',
#             }
#         ],
#         'test_start': time.time(),
#         'artifacts_base_dir': './logs'
#     }
#     data_session = DataSession(config=config)
#
#     metric_meta = {
#         'type': 'metrics',
#         'name': 'cpu_usage',
#         'hostname': 'localhost',
#         'some_meta_key': 'some_meta_value'
#     }
#
#     metric_obj = data_session.new_true_metric('name', **metric_meta)
#     time.sleep(1)
#     df = pd.DataFrame([[123, 123.123, "trash"]], columns=['ts', 'value', 'trash'])
#     metric_obj.put(df)
#     df2 = pd.DataFrame([[456, 456.456]], columns=['ts', 'value'])
#     metric_obj.put(df2)
#     time.sleep(10)
#     df = pd.DataFrame([[123, 123.123]], columns=['ts', 'value'])
#     metric_obj.put(df)
#     df2 = pd.DataFrame([[456, 456.456]], columns=['ts', 'value'])
#     metric_obj.put(df2)
#     time.sleep(10)
#     data_session.close(test_end=time.time())


if __name__ == '__main__':
    logging.basicConfig(level='DEBUG')
    logger = logging.getLogger(__name__)
    # usage_sample()
