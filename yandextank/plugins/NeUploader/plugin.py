""" Plugin uploading metrics from yandextank to Luna. """
import logging
from netort.data_manager import DataSession

from yandextank.plugins.Phantom.reader import string_to_df_microsec
from ...common.interfaces import AbstractPlugin,\
    MonitoringDataListener

logger = logging.getLogger(__name__)  # pylint: disable=C0103


class Plugin(AbstractPlugin, MonitoringDataListener):
    SECTION = 'neuploader'

    columns = ['interval_real', 'connect_time', 'send_time',
               'latency', 'receive_time', 'interval_event']

    def __init__(self, core, cfg, name):
        super(Plugin, self).__init__(core, cfg, name)
        self._is_telegraf = None
        self.clients_cfg = [{'type': 'luna',
                             'api_address': self.cfg.get('api_address'),
                             'db_name': self.cfg.get('db_name')}]
        self.metrics_ids = {}  # map of case names and metric local ids

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
            self.uploader = self.get_uploader()

    def cleanup(self):
        uploader_metainfo = self.map_uploader_tags(self.core.status.get('uploader'))
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
        # TODO: create cases
        return retcode

    @property
    def is_telegraf(self):
        return True

    def metric_generator(self, col, case):
        """
        Generator of metric objects:
        Checks existent metrics and creates new aggregated metric if it does not exist.
        :param col:  str with column name
        :param case: str with case name
        :return: metric object
        """

        metric_obj = self.metrics_ids[col].get(case)
        if not metric_obj:
            parent = self.metrics_ids[col].get('overall')
            metric_obj = self.data_session.new_aggregated_metric('metric {} {}'.format(col, case), parent=parent)
            self.metrics_ids[col][case] = metric_obj.local_id
        return metric_obj

    def get_uploader(self):
        """
        Creates metric_obj on every metric for every case in DataFrame and puts all them to queue.
        :return: upload_df function
        """

        self.metrics_ids = {column: {} for column in self.columns}

        def upload_df(df):
            """
            Every metric in dataframe should be aggregated twice if it has not null tag column
            :param df: input chunk with DataFrame
            :return: function
            """
            df_cases_set = set([row.tag for row in df.itertuples() if row.tag])

            for column in self.columns:
                overall_metric_obj = self.metric_generator(column, 'overall')
                overall_metric_obj.put(df)

                for case_name in df_cases_set:
                    case_metric_obj = self.metric_generator(column, case_name)
                    self.metrics_ids[column][case_name] = case_metric_obj.local_id

                    result_df = self.filter_df_by_case(df, case_name)
                    result_df['value'] = result_df[column]
                    case_metric_obj.put(result_df)

        return upload_df

    @staticmethod
    def filter_df_by_case(df, case):
        """
        Filter dataframe by case name. If case is 'overall', return the whole dataframe.
        :param df: DataFrame
        :param case: str with case name
        :return: DataFrame
        """
        return df if case == 'overall' else df.loc[df['tag'] == case]

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
