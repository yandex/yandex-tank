from collections import OrderedDict

from requests import HTTPError, ConnectionError
from requests.exceptions import Timeout, TooManyRedirects

from ..common.interfaces import AbstractClient, QueueWorker
from ..common.util import pretty_print, thread_safe_property

from retrying import retry

import json
import pkg_resources
import logging
import requests
import threading
import time
import six
import pandas as pd
import datetime
import os
if six.PY2:
    import Queue as queue
else:
    # noinspection PyUnresolvedReferences
    import queue

requests.packages.urllib3.disable_warnings()

logger = logging.getLogger(__name__)


RETRY_ARGS = dict(
    stop_max_delay=30000,
    wait_fixed=3000,
    stop_max_attempt_number=10
)

SLEEP_ON_EMPTY = 0.2  # pause in seconds before checking empty queue on new items
MAX_DF_LENGTH = 10000  # Size of chunk is 10k rows, it's approximately 0.5Mb in csv


@retry(**RETRY_ARGS)
def send_chunk(session, req, timeout=5):
    r = session.send(req, verify=False, timeout=timeout)
    logger.debug('Request %s code %s. Text: %s', r.url, r.status_code, r.text)
    return r


def if_not_failed(func):
    def wrapped(self, *a, **kw):
        if self.failed.is_set():
            logger.warning('Luna client is disabled')
            return
        else:
            return func(self, *a, **kw)
    return wrapped


class LunaClient(AbstractClient):
    create_metric_path = '/create_metric/'
    update_metric_path = '/update_metric/'
    upload_metric_path = '/upload_metric/?query='  # production
    create_job_path = '/create_job/'
    update_job_path = '/update_job/'
    close_job_path = '/close_job/'
    symlink_artifacts_path = 'luna'

    def __init__(self, meta, job):
        super(LunaClient, self).__init__(meta, job)
        logger.debug('Luna client local id: %s', self.local_id)
        self.dbname = meta.get('db_name', 'luna')
        self.failed = threading.Event()
        self.public_ids = {}
        self.luna_columns = ['key_date', 'tag']
        self.key_date = "{key_date}".format(key_date=datetime.datetime.now().strftime("%Y-%m-%d"))
        self._interrupted = threading.Event()
        self.register_worker = RegisterWorkerThread(self)
        self.register_worker.start()
        self.worker = WorkerThread(self)
        self.worker.start()
        self.session = requests.session()
        self.clickhouse_user = meta.get('clickhouse_user', 'lunapark')
        self.clickhouse_key = meta.get('clickhouse_key', 'lunapark')
        self.max_df_len = meta.get('max_df_len') or MAX_DF_LENGTH

        if self.meta.get('api_address'):
            self.api_address = self.meta.get('api_address')
        else:
            raise RuntimeError('Api address SHOULD be specified')
        self._job_number = None

    @thread_safe_property
    def job_number(self):
        if not self.failed.is_set():
            try:
                _job_number = self.create_job()
                self.__test_id_link_to_jobno(_job_number)
            except (HTTPError, ConnectionError, Timeout, TooManyRedirects):
                logger.error('Failed to create Luna job', exc_info=True)
                self.failed.set()
                self.worker.interrupt()
                self.interrupt()
            else:
                return _job_number

    def put(self, data_type, df):   # noqa: PLE0202
        if not self.failed.is_set():
            self.pending_queue.put((data_type, df))
        else:
            logger.debug('Skipped incoming data chunk due to failures')

    @if_not_failed
    def create_job(self):
        """ Create public Luna job

        Returns:
            job_id (str): Luna job id
        """
        my_user_agent = None
        try:
            my_user_agent = pkg_resources.require('yandextank.contrib.netort.netort')[0].version
        except pkg_resources.DistributionNotFound:
            my_user_agent = 'DistributionNotFound'
        finally:
            headers = {
                "User-Agent": "Uploader/{uploader_ua}, {upward_ua}".format(
                    upward_ua=self.meta.get('user_agent', ''),
                    uploader_ua=my_user_agent
                )
            }
        request_data = dict(
            self.data_session.tankapi_info,
            test_start=int(self.data_session.test_start),
            configs=self._get_encoded_configs_content()
        )
        if request_data['host'] is None or request_data['port'] is None:
            logger.warning('Tankapi host and/or port are unspecified. Artifacts & configs would be unavailable in Luna')
        req = requests.Request(
            'POST',
            "{api_address}{path}".format(
                api_address=self.api_address,
                path=self.create_job_path
            ),
            headers=headers,
            data=request_data
        )
        prepared_req = req.prepare()
        logger.debug('Prepared create_job request:\n%s', pretty_print(prepared_req))

        response = send_chunk(self.session, prepared_req)
        logger.debug('Luna create job status: %s', response.status_code)
        response.raise_for_status()
        logger.debug('Answ data: %s', response.content)
        job_id = response.content.decode('utf-8') if isinstance(response.content, bytes) else response.content
        if not job_id:
            self.failed.set()
            self.worker.interrupt()
            raise ValueError('Luna returned answer without jobid: %s', response.content)
        else:
            logger.info('Luna job created: %s', job_id)
            return job_id

    def _get_encoded_configs_content(self):
        config_dir = self.data_session.artifacts_base_dir
        config_filenames = self.data_session.config_filenames
        files = config_filenames & set(os.listdir(config_dir))
        result = {}
        for file_name in files:
            with open(os.path.join(config_dir, file_name)) as file:
                content = file.read()
                result[file_name] = content
        return json.dumps(result)

    @if_not_failed
    def update_job(self, meta):
        req = requests.Request(
            'POST',
            "{api_address}{path}?job={job}".format(
                api_address=self.api_address,
                path=self.update_job_path,
                job=self.job_number
            ),
            json=meta
        )
        prepared_req = req.prepare()
        logger.debug('Prepared update_job request:\n%s', pretty_print(prepared_req))
        response = send_chunk(self.session, prepared_req)
        logger.debug('Update job status: %s', response.status_code)
        logger.debug('Answ data: %s', response.content)

    @if_not_failed
    def update_metric(self, meta):
        for metric_tag, metric_obj in self.data_session.manager.metrics.items():
            if not metric_obj.tag:
                logger.debug('Metric %s has no public tag, skipped updating metric', metric_tag)
                continue
            req = requests.Request(
                'POST',
                "{api_address}{path}?tag={tag}".format(
                    api_address=self.api_address,
                    path=self.update_metric_path,
                    tag=metric_obj.tag
                ),
            )
            req.data = meta
            # FIXME: should be called '_offset' after volta-service production is updated;
            if 'sys_uts_offset' in meta and metric_obj.type == 'metrics':
                req.data['offset'] = meta['sys_uts_offset']
            elif 'log_uts_offset' in meta and metric_obj.type == 'events':
                req.data['offset'] = meta['log_uts_offset']
            prepared_req = req.prepare()
            logger.debug('Prepared update_metric request:\n%s', pretty_print(prepared_req))
            response = send_chunk(self.session, prepared_req)
            logger.debug('Update metric status: %s', response.status_code)
            logger.debug('Answ data: %s', response.content)

    @if_not_failed
    def _close_job(self, duration):
        req = requests.Request(
            'GET',
            "{api_address}{path}".format(
                api_address=self.api_address,
                path=self.close_job_path,
            ),
            params={'job': self.job_number,
                    'duration': int(duration)}
        )
        prepared_req = req.prepare()
        logger.debug('Prepared close_job request:\n%s', pretty_print(prepared_req))
        response = send_chunk(self.session, prepared_req)
        logger.debug('Update job status: %s', response.status_code)

    def __test_id_link_to_jobno(self, jobno):
        """  create symlink local_id <-> public_id  """
        # TODO: fix symlink to local_id <-> luna_id
        link_dir = os.path.join(self.data_session.artifacts_base_dir, self.symlink_artifacts_path)
        if not jobno:
            logger.info('Public test id not available, skipped symlink creation for %s', self.symlink_artifacts_path)
            return
        if not os.path.exists(link_dir):
            os.makedirs(link_dir)
        try:
            os.symlink(
                os.path.join(
                    os.path.relpath(self.data_session.artifacts_base_dir, link_dir), self.data_session.job_id
                ),
                os.path.join(link_dir, str(jobno))
            )
        except OSError:
            logger.warning(
                'Unable to create %s/%s symlink for test: %s',
                self.symlink_artifacts_path, jobno, self.data_session.job_id
            )
        else:
            logger.debug(
                'Symlink %s/%s created for job: %s',
                self.symlink_artifacts_path, jobno, self.data_session.job_id
            )

    def close(self, test_end):
        self.worker.stop()
        if not self.job_number:
            logger.info('Try to interrupt queue')
            self.worker.interrupt()
        if not self.worker.is_finished():
            logger.debug('Processing pending uploader queue... qsize: %s', self.pending_queue.qsize())
        logger.info('Joining luna client metric uploader thread...')
        self.worker.join()
        logger.info('Joining luna client metric registration thread...')
        self.register_worker.stop()
        self.register_worker.join()
        self._close_job(duration=test_end-self.data_session.test_start)
        # FIXME hardcoded host
        # FIXME we dont know front hostname, because api address now is clickhouse address
        logger.info('Luna job url: %s%s', 'https://luna.yandex-team.ru/tests/', self.job_number)
        logger.info('Luna client done its work')

    def interrupt(self):
        logger.warning('Luna client work was interrupted.')
        self.put = lambda *a, **kw: None
        self.register_worker.interrupt()
        self.worker.interrupt()


class RegisterWorkerThread(threading.Thread):
    """ Register metrics metadata, get public_id from luna and create map local_id <-> public_id """
    def __init__(self, client):
        """
        :type client: LunaClient
        """
        super(RegisterWorkerThread, self).__init__()
        self.client = client
        self.session = requests.session()
        self.metrics_to_register = OrderedDict()
        self.lock = threading.Lock()
        self._finished = threading.Event()
        self._stopped = threading.Event()
        self._interrupted = threading.Event()
        # Register all metrics not registered yet
        for metric_id in self.client.data_session.manager.metrics:
            if metric_id not in self.client.public_ids:
                metric = self.client.data_session.manager.get_metric_by_id(metric_id)
                self.metrics_to_register[metric_id] = metric

    def stop(self):
        self._stopped.set()

    def interrupt(self):
        self._stopped.set()
        self._interrupted.set()

    def is_finished(self):
        return self._finished.is_set()

    def register(self, metric):
        self.lock.acquire()
        self.metrics_to_register[metric.local_id] = metric
        self.lock.release()

    def run(self):
        while not self._stopped.is_set():
            self._process_pending_queue()
        while len(self.metrics_to_register) > 0 and not self._interrupted.is_set():
            self._process_pending_queue()
        if len(self.metrics_to_register) > 0:
            self.metrics_to_register.clear()
        self._finished.set()

    def _process_pending_queue(self):
        try:
            self.lock.acquire()
            local_id, metric = self.metrics_to_register.popitem(last=False)
            self.lock.release()
            if local_id not in self.client.public_ids:
                if metric.parent is not None and metric.parent.local_id not in self.client.public_ids:
                    logger.debug('Metric {} waiting for parent metric {} to be registered'.format(metric.local_id,
                                                                                                  metric.parent.local_id))
                    self.register(metric.parent)
                    self.register(metric)
                else:
                    metric.tag = self._register_metric(metric)
                    logger.debug('Successfully received tag %s for metric.local_id: %s (%s)',
                                 metric.tag, metric.local_id, metric.meta)
                    self.client.public_ids[metric.local_id] = metric.tag
        except (HTTPError, ConnectionError, Timeout, TooManyRedirects):
            self.lock.release()
            logger.error("Luna service unavailable", exc_info=True)
            self.client.interrupt()
        except KeyError:
            self.lock.release()
            time.sleep(0.5)

    def _register_metric(self, metric):
        json = {
            'job': self.client.job_number,
            'type': metric.type.table_name,
            'types': [t.table_name for t in metric.data_types],
            'local_id': metric.local_id,
            'meta': metric.meta,
            'parent': self.client.public_ids[metric.parent.local_id] if metric.parent is not None else None,
            'case': metric.case
        }
        req = requests.Request(
            'POST',
            "{api_address}{path}".format(
                api_address=self.client.api_address,
                path=self.client.create_metric_path
            ),
            json=json
        )
        prepared_req = req.prepare()
        logger.debug('Prepared create_metric request:\n%s', pretty_print(prepared_req))
        response = send_chunk(self.session, prepared_req)
        response.raise_for_status()
        if not response.content:
            raise HTTPError('Luna did not return uniq_id for metric registration: %s', response.content)
        else:
            return response.content.decode('utf-8') if six.PY3 else response.content


# noinspection PyTypeChecker
class WorkerThread(QueueWorker):
    """ Process data """
    def __init__(self, client):
        """
        :type client: LunaClient
        """
        super(WorkerThread, self).__init__(client.pending_queue)
        self.data = {'max_length': 0}
        self.client = client
        self.session = requests.session()

    def run(self):
        while not self._stopped.is_set():
            self._process_pending_queue()
        while self.queue.qsize() > 0 and not self._interrupted.is_set():
            self._process_pending_queue(progress=True)
        while self.queue.qsize() > 0:
            self.queue.get_nowait()
        if self.data['max_length'] != 0:
            self.__upload_data()
        self._finished.set()

    def _process_pending_queue(self, progress=False):
        try:
            data_type, raw_df = self.queue.get_nowait()
            if progress:
                logger.info("{} entries in queue remaining".format(self.client.pending_queue.qsize()))
        except queue.Empty:
            time.sleep(SLEEP_ON_EMPTY)
        except KeyboardInterrupt:
            self.interrupt()
        else:
            self.__update_df(data_type, raw_df)

    def __update_max_length(self, new_length):
        return new_length if self.data['max_length'] < new_length else self.data['max_length']

    def __update_df(self, data_type, df):
        metric_local_id = df['metric_local_id'].iloc[0]
        metric = self.client.data_session.manager.get_metric_by_id(metric_local_id)

        if not metric:
            logger.warning('Received unknown metric: %s! Ignored.', metric_local_id)
            return pd.DataFrame([])

        if metric.local_id not in self.client.public_ids:
            # no public_id yet, put it back
            self.client.put(data_type, df)
            self.client.register_worker.register(metric)
            return pd.DataFrame([])

        df.loc[:, 'key_date'] = self.client.key_date
        df.loc[:, 'tag'] = self.client.public_ids[metric.local_id]

        if not df.empty:
            table_name = data_type.table_name
            if not self.data.get(table_name):
                self.data[table_name] = {
                    'dataframe': df,
                    'columns': self.client.luna_columns + data_type.columns,
                }
            else:
                self.data[table_name]['dataframe'] = pd.concat([self.data[table_name]['dataframe'], df])
            self.data['max_length'] = self.__update_max_length(len(self.data[table_name]['dataframe']))

        if self.data['max_length'] >= self.client.max_df_len:
            self.__upload_data()

    def __upload_data(self):
        for table_name, data in self.data.items():
            if table_name != 'max_length':
                logger.debug('Length of data for %s is %s', table_name, len(data['dataframe']))
                try:
                    self.__send_upload(table_name, data['dataframe'], data['columns'])

                except ConnectionError:
                    logger.warning('Failed to upload data to luna backend after consecutive retries. '
                                   'Attempt to send data in two halves')
                    try:
                        self.__send_upload(
                            table_name,
                            data['dataframe'].head(len(data['dataframe']) // 2),
                            data['columns']
                        )
                        self.__send_upload(
                            table_name,
                            data['dataframe'].tail(len(data['dataframe']) - len(data['dataframe']) // 2),
                            data['columns']
                        )
                    except ConnectionError:
                        logger.warning('Failed to upload data to luna backend after consecutive retries. Sorry.')
                        return

                self.data = dict()
                self.data['max_length'] = 0

    def __send_upload(self, table_name, df, columns):
        body = df.to_csv(
            sep='\t',
            header=False,
            index=False,
            na_rep='',
            columns=columns
        )
        req = requests.Request(
            'POST', "{api}{data_upload_handler}{query}".format(
                api=self.client.api_address,  # production proxy
                data_upload_handler=self.client.upload_metric_path,
                query="INSERT INTO {db}.{table} FORMAT TSV".format(db=self.client.dbname,
                                                                   table=table_name)  # production
            )
        )
        req.data = body
        prepared_req = req.prepare()

        try:
            resp = send_chunk(self.session, prepared_req)
            resp.raise_for_status()
            logger.info('Update table %s with %s rows -- successful', table_name, df.shape[0])

        except ConnectionError:
            raise
        except (HTTPError, Timeout, TooManyRedirects) as e:
            # noinspection PyUnboundLocalVariable
            logger.warning('Failed to upload data to luna. Dropped some data.\n{}'.
                           format(resp.content if isinstance(e, HTTPError) else 'no response'))
            logger.debug(
                'Failed to upload data to luna backend after consecutive retries.\n'
                'Dropped data head: \n%s', df.head(), exc_info=True
            )
            self.client.interrupt()
