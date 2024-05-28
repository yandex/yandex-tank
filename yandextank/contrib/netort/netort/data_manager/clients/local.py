from ..common.interfaces import AbstractClient

import io
import os
import logging
import json
import threading
try:
    import queue
except ImportError:
    import Queue as queue
import time
from builtins import str

logger = logging.getLogger(__name__)

"""
output artifact sample:

{"dtypes": {"ts": "int64", "value": "float64"}, "type": "metric", "names": ["ts", "value"]}
123	123.123
456	456.456
123	123.123
456	456.456

output meta.json sample:
{
    "metrics": {
        "metric_d12dab4f-e4ef-4c47-89e6-859f73737c64": {
            "dtypes": {
                "ts": "int64",
                "value": "float64"
            },
            "meta": {
                "hostname": "localhost",
                "name": "cpu_usage",
                "some_meta_key": "some_meta_value",
                "type": "metrics"
            },
            "names": [
                "ts",
                "value"
            ],
            "type": "metrics"
        },
    },
    "job_meta": {
        "key": "valueZ",
    }
}
"""


class LocalStorageClient(AbstractClient):
    separator = '\t'
    metrics_meta_fname = 'meta.json'

    def __init__(self, meta, job):
        super(LocalStorageClient, self).__init__(meta, job)
        self.registered_meta = {}

        self.processing_thread = ProcessingThread(self)
        self.processing_thread.daemon = True
        self.processing_thread.start()

    def put(self, data_type, df):
        if df is not None:
            self.pending_queue.put((data_type, df))

    def close(self, test_end):
        self.processing_thread.stop()
        logger.info('Joining local client processing thread...')
        self.processing_thread.join()
        logger.info('Local client finished its work. Artifacts are here %s', self.data_session.artifacts_dir)


class ProcessingThread(threading.Thread):
    """ Process data """
    def __init__(self, client):
        super(ProcessingThread, self).__init__()
        self._finished = threading.Event()
        self._interrupted = threading.Event()
        self.client = client
        self.file_streams = {}

    def __create_artifact(self, metric_full_name):
        self.file_streams[metric_full_name] = io.open(
            os.path.join(
                self.client.data_session.artifacts_dir, "{}.data".format(metric_full_name)
            ),
            mode='w'
        )

    def run(self):
        while not self._interrupted.is_set():
            self.__process_pending_queue()
        logger.info(
            'File writer thread interrupted, finishing work and trying to write the rest of data, qsize: %s',
            self.client.pending_queue.qsize()
        )
        self.__process_pending_queue()
        self.__close_files_and_dump_meta()
        self._finished.set()

    def __process_pending_queue(self):
        try:
            data_type, incoming_df = self.client.pending_queue.get_nowait()
            df = incoming_df.copy()[data_type.columns]
        except queue.Empty:
            time.sleep(1)
        else:
            for metric_local_id, df_grouped_by_id in df.groupby(level=0, sort=False):
                metric = self.client.data_session.manager.get_metric_by_id(metric_local_id)
                if not metric:
                    logger.warning('Received unknown metric id: %s', metric_local_id)
                    return
                metric_full_name = '{}_{}'.format(data_type.table_name, metric_local_id)
                if metric_full_name not in self.file_streams:
                    logger.debug('Creating artifact file for %s', metric_full_name)
                    self.__create_artifact(metric_full_name)
                    this_metric_meta = {
                        'type': data_type.__name__,
                        'names': data_type.columns,
                        'dtypes': df.dtypes.apply(lambda x: x.name).to_dict(),
                        'meta': metric.meta
                    }
                    self.client.registered_meta[metric_full_name] = this_metric_meta
                    artifact_file_header = json.dumps(this_metric_meta)
                    self.file_streams[metric_full_name].write("%s\n" % artifact_file_header)
                csv_data = df_grouped_by_id.to_csv(
                    sep=self.client.separator,
                    header=False,
                    index=False,
                    na_rep="",
                    columns=data_type.columns,
                )
                try:
                    self.file_streams[metric_full_name].write(
                        str(csv_data)
                    )
                    self.file_streams[metric_full_name].flush()
                except ValueError:
                    logger.warning('Failed to write metrics to file, maybe file is already closed?', exc_info=True)

    def is_finished(self):
        return self._finished

    def __close_files_and_dump_meta(self):
        [self.file_streams[file_].close() for file_ in self.file_streams]
        with open(os.path.join(self.client.data_session.artifacts_dir, self.client.metrics_meta_fname), 'w') as meta_f:
            json.dump(
                {"metrics": self.client.registered_meta, "job_meta": self.client.meta},
                meta_f,
                indent=4,
                sort_keys=True
            )

    def stop(self):
        self._interrupted.set()
