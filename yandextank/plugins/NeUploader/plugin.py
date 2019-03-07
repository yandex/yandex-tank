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
        self.clients_cfg = [{'type': 'luna', 'api_address': self.cfg.get('api_address')}]

    def configure(self):
        pass

    def start_test(self):
        self.data_session = DataSession({'clients': self.clients_cfg})
        self.add_cleanup(self.data_session.close)
        self.data_session.update_job({'name': self.cfg.get('test_name')})
        col_map_aggr = {name: 'metric %s' % name for name in
                        ['interval_real', 'connect_time', 'send_time', 'latency',
                         'receive_time', 'interval_event']}
        self.uploader = get_uploader(self.data_session, col_map_aggr, True)
        self.reader = self.core.job.generator_plugin.get_reader(parser=string_to_df_microsec)

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
