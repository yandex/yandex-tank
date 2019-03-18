import logging
from netort.data_manager import DataSession

from yandextank.plugins.Phantom.reader import string_to_df_microsec
from ...common.interfaces import AbstractPlugin,\
    MonitoringDataListener

logger = logging.getLogger(__name__)  # pylint: disable=C0103


class Plugin(AbstractPlugin, MonitoringDataListener):
    SECTION = 'neuploader'

    def __init__(self, core, cfg, name):
        super(Plugin, self).__init__(core, cfg, name)
        self._is_telegraf = None
        self.clients_cfg = [{'type': 'luna',
                             'api_address': self.cfg.get('api_address'),
                             'db_name': self.cfg.get('db_name')}]

    def configure(self):
        pass

    def start_test(self):
        try:
            self.reader = self.core.job.generator_plugin.get_reader(parser=string_to_df_microsec)
        except TypeError:
            logger.error('Generator plugin does not support NeUploader')
            self.is_test_finished = lambda: -1
            self.reader = []
        else:
            self.data_session = DataSession({'clients': self.clients_cfg})
            self.add_cleanup(self.cleanup)
            self.data_session.update_job({'name': self.cfg.get('test_name')})
            col_map_aggr = {name: 'metric %s' % name for name in
                            ['interval_real', 'connect_time', 'send_time', 'latency',
                             'receive_time', 'interval_event']}
            self.uploader = get_uploader(self.data_session, col_map_aggr, True)

    def cleanup(self):
        uploader_metainfo = self.map_uploader_tags(self.core.status.get('uploader').items())
        self.data_session.update_job(uploader_metainfo)
        self.data_session.close()

    def is_test_finished(self):
        df = next(self.reader)
        if df is not None:
            self.uploader(df)
        return -1

    def monitoring_data(self, data_list):
        pass

    def post_process(self, retcode):
        for chunk in self.reader:
            if chunk is not None:
                self.uploader(chunk)
        return retcode

    @property
    def is_telegraf(self):
        return True

    @staticmethod
    def map_uploader_tags(uploader_tags):
        return dict(
            [
                ('component', uploader_tags.get('component')),
                ('description', uploader_tags.get('job_dsc')),
                ('name', uploader_tags.get('job_name')),
                ('person', uploader_tags.get('person')),
                ('task', uploader_tags.get('task')),
                ('version', uploader_tags.get('version')),
                ('lunapark_jobno', uploader_tags.get('job_no'))
            ] + [
                (k, v) for k, v in uploader_tags.get('meta', {}).items()
            ]
        )


def get_uploader(data_session, column_mapping, overall_only=False):
    """
    :type column_mapping: dict
    :type data_session: DataSession
    """
    overall = {col_name: data_session.new_aggregated_metric(name + ' overall')
               for col_name, name in column_mapping.items()}

    def upload_df(df):
        for col_name, metric in overall.items():
            df['value'] = df[col_name]
            metric.put(df)
    return upload_df
