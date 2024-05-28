import logging
import requests
import threading
import time
import datetime
import os
import pkg_resources
try:
    import queue
except ImportError:
    import Queue as queue

from retrying import retry, RetryError

from ..common.interfaces import AbstractClient
from ..common.util import pretty_print, thread_safe_property

from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


logger = logging.getLogger(__name__)

RETRY_ARGS = dict(
    wrap_exception=True,
    stop_max_delay=10000,
    wait_fixed=1000,
    stop_max_attempt_number=5
)


@retry(**RETRY_ARGS)
def send_chunk(session, req, timeout=5):
    r = session.send(req, verify=False, timeout=timeout)
    logger.debug('Request %s code %s. Text: %s', r.url, r.status_code, r.text)
    r.raise_for_status()
    return r


class LunaparkVoltaClient(AbstractClient):
    create_job_path = '/mobile/create_job.json'
    update_job_path = '/mobile/update_job.json'
    metric_update = ''  # FIXME
    metric_upload = '/api/volta/?query='
    dbname = 'volta'
    symlink_artifacts_path = 'lunapark_volta'
    data_types_to_tables = {
        'current': 'currents',
        'syncs': 'syncs',
        'events': 'events',
        'metrics': 'metrics',
        'fragments': 'fragments',
        'unknown': 'logentries'
    }
    # aliases
    data_types_to_tables.update(
        {
            'currents': data_types_to_tables['current'],
            'sync': data_types_to_tables['syncs'],
            'event': data_types_to_tables['events'],
            'metric': data_types_to_tables['metrics'],
            'fragment': data_types_to_tables['fragments'],
            'logentries': data_types_to_tables['unknown']
        }
    )
    clickhouse_output_fmt = {
        'current': ['ts', 'value'],
        'syncs': ['ts', 'log_uts', 'app', 'tag', 'message'],
        'events': ['ts', 'log_uts', 'app', 'tag', 'value'],
        'metrics': ['ts', 'log_uts', 'app', 'tag', 'value'],
        'fragments': ['ts', 'log_uts', 'app', 'tag', 'message'],
        'unknown': ['ts', 'value']
    }
    # aliases
    clickhouse_output_fmt.update(
        {
            'currents': clickhouse_output_fmt['current'],
            'sync': clickhouse_output_fmt['syncs'],
            'event': clickhouse_output_fmt['events'],
            'metric': clickhouse_output_fmt['metrics'],
            'fragment': clickhouse_output_fmt['fragments'],
            'logentries': clickhouse_output_fmt['unknown']
        }
    )

    def __init__(self, meta, job):
        super(LunaparkVoltaClient, self).__init__(meta, job)
        self.failed = threading.Event()
        if self.meta.get('api_address'):
            self.api_address = self.meta.get('api_address')
        else:
            raise RuntimeError('Api address must be specified')
        self.clickhouse_cols = ['key_date', 'test_id']
        self.task = self.meta.get('task', 'LOAD-272')
        self.session = requests.session()
        self.key_date = "{key_date}".format(key_date=datetime.datetime.now().strftime("%Y-%m-%d"))
        self._job_number = None
        self.worker = WorkerThread(self)
        self.worker.start()
        logger.info('Lunapark Volta public job id: %s', self.job_number)

    @thread_safe_property
    def job_number(self):
        if self.failed.is_set():
            return
        if not self._job_number:
            try:
                self._job_number = self.create_job()
                self.__test_id_link_to_jobno()
            except RetryError:
                logger.debug('Failed to create lunapark volta job', exc_info=True)
                logger.warning('Failed to create lunapark volta job')
                self.failed.set()
            else:
                return self._job_number
        else:
            return self._job_number

    def __test_id_link_to_jobno(self):
        """  create symlink local_id <-> public_id  """
        link_dir = os.path.join(self.data_session.artifacts_base_dir, self.symlink_artifacts_path)
        if not self._job_number:
            logger.info('Public test id not available, skipped symlink creation for %s', self.symlink_artifacts_path)
            return
        if not os.path.exists(link_dir):
            os.makedirs(link_dir)
        try:
            os.symlink(
                os.path.join(
                    os.path.relpath(self.data_session.artifacts_base_dir, link_dir), self.data_session.job_id
                ),
                os.path.join(link_dir, str(self.job_number))
            )
        except OSError:
            logger.warning(
                'Unable to create %s/%s symlink for test: %s',
                self.symlink_artifacts_path, self.job_number, self.data_session.job_id
            )
        else:
            logger.debug(
                'Symlink %s/%s created for job: %s', self.symlink_artifacts_path, self.job_number, self.data_session.job_id
            )

    def put(self, data_type, df):
        if not self.failed.is_set():
            self.pending_queue.put((data_type, df))
        else:
            logger.debug('Skipped incoming data chunk due to failures')

    def create_job(self):
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
        req = requests.Request(
            'POST',
            "{api_address}{path}".format(
                api_address=self.api_address,
                path=self.create_job_path
            ),
            headers=headers
        )
        req.data = {
            'key_date': self.key_date,
            'test_id': "{key_date}_{local_job_id}".format(
                key_date=self.key_date,
                local_job_id=self.data_session.job_id
            ),
            'task': self.task,
            'version': "2"
        }
        prepared_req = req.prepare()
        logger.debug('Prepared lunapark_volta create_job request:\n%s', pretty_print(prepared_req))

        response = send_chunk(self.session, prepared_req)
        logger.debug('Lunapark volta create job status: %s', response.status_code)
        logger.debug('Answ data: %s', response.json())
        job_id = response.json().get('jobno')
        if not job_id:
            logger.warning('Create job answ data: %s', response.json())
            self.failed.set()
            raise ValueError('Lunapark volta returned answer without jobno: %s', response.json())
        else:
            logger.info('Lunapark volta job created: %s', job_id)
            return job_id

    def update_job(self, meta):
        req = requests.Request(
            'POST',
            "{api_address}{path}".format(
                api_address=self.api_address,
                path=self.update_job_path
            ),
        )
        req.data = meta
        req.data['test_start'] = self.data_session.test_start
        req.data['test_id'] = "{key_date}_{local_job_id}".format(
            key_date=self.key_date,
            local_job_id=self.data_session.job_id
        ),
        prepared_req = req.prepare()
        logger.debug('Prepared update_job request:\n%s', pretty_print(prepared_req))
        response = send_chunk(self.session, prepared_req)
        logger.debug('Update job status: %s', response.status_code)
        logger.debug('Answ data: %s', response.content)

    def get_info(self):
        """ mock """
        pass

    def close(self, test_end):
        self.worker.stop()
        while not self.worker.is_finished():
            logger.debug('Processing pending uploader queue... qsize: %s', self.pending_queue.qsize())
        logger.debug('Joining lunapark_volta metric uploader thread...')
        self.worker.join()


class WorkerThread(threading.Thread):
    """ Process data """
    def __init__(self, client):
        super(WorkerThread, self).__init__()
        self._finished = threading.Event()
        self._interrupted = threading.Event()
        self.client = client
        self.session = requests.session()

    def run(self):
        while not self._interrupted.is_set():
            self.__process_pending_queue()
        logger.info('Lunapark volta uploader thread main loop interrupted, '
                    'finishing work and trying to send the rest of data, qsize: %s',
                    self.client.pending_queue.qsize())
        self.__process_pending_queue()
        self._finished.set()

    def __process_pending_queue(self):
        exec_time_start = time.time()
        try:
            incoming_df = self.client.pending_queue.get_nowait()
            df = incoming_df.copy()
        except queue.Empty:
            time.sleep(1)
        else:
            for metric_local_id, df_grouped_by_id in df.groupby(level=0, sort=False):
                df_grouped_by_id['key_date'] = self.client.key_date
                df_grouped_by_id['test_id'] = "{key_date}_{local_job_id}".format(
                    key_date=self.client.key_date,
                    local_job_id=self.client.data_session.job_id
                )
                metric = self.client.data_session.manager.get_metric_by_id(metric_local_id)
                if metric.type == 'events':
                    try:
                        gb = df_grouped_by_id.groupby('custom_metric_type', sort=False)
                    except KeyError:
                        self.__send_this_type(df_grouped_by_id, 'unknown')
                    else:
                        for gb_name, gb_frame in gb:
                            self.__send_this_type(gb_frame, gb_name)
                elif metric.type == 'metrics' and metric.meta.get('name') == 'current':
                    self.__send_this_type(df_grouped_by_id, 'current')
                else:
                    logger.debug('Dropped data of type %s, %s probably monitoring or other user custom metrics...',
                                 metric.type, metric.meta.get('name'))
        logger.debug('Lunapark volta client processing took %.2f ms', (time.time() - exec_time_start) * 1000)

    def __send_this_type(self, df, metric_type):
        try:
            body = df.to_csv(
                sep='\t',
                header=False,
                index=False,
                na_rep="",
                columns=self.client.clickhouse_cols + self.client.clickhouse_output_fmt[metric_type]
            )
        except Exception:
            logger.info('Exc: %s', exc_info=True)
        req = requests.Request(
            'POST', "{api}{data_upload_handler}{query}".format(
                api=self.client.api_address,
                data_upload_handler=self.client.metric_upload,
                query="INSERT INTO {table} FORMAT TSV".format(
                    table="{db}.{type}".format(
                        db=self.client.dbname,
                        type=self.client.data_types_to_tables[metric_type]
                    )
                )
            )
        )
        req.data = body
        prepared_req = req.prepare()
        try:
            send_chunk(self.session, prepared_req)
        except RetryError:
            logger.warning(
                'Failed to upload data to lunapark backend. Dropped some data.'
            )
            logger.debug(
                'Failed to upload data to luna, dropped data: %s', df, exc_info=True
            )
            return

    def is_finished(self):
        return self._finished

    def stop(self):
        self._interrupted.set()
        # FIXME
        logger.info('Lunapark Volta public job id: http://lunapark.yandex-team.ru/mobile/%s', self.client.job_number)
