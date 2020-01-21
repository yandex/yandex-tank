import logging

import pandas
from netort.data_manager import DataSession, thread_safe_property

from yandextank.plugins.Phantom.reader import string_to_df_microsec
from yandextank.common.interfaces import AbstractPlugin,\
    MonitoringDataListener

logger = logging.getLogger(__name__)  # pylint: disable=C0103


class Plugin(AbstractPlugin, MonitoringDataListener):
    SECTION = 'neuploader'
    importance_high = {
        'interval_real',
        'proto_code',
        'net_code'
    }
    OVERALL = '__overall__'

    def __init__(self, core, cfg, name):
        super(Plugin, self).__init__(core, cfg, name)
        self._is_telegraf = None
        self.clients_cfg = [{'type': 'luna',
                             'api_address': self.cfg.get('api_address'),
                             'db_name': self.cfg.get('db_name')}]
        self.metrics_objs = {}  # map of case names and metric objects
        self.monitoring_metrics = {}
        self._col_map = None
        self._data_session = None

    def configure(self):
        pass

    def start_test(self):
        try:
            self.reader = self.core.job.generator_plugin.get_reader(parser=string_to_df_microsec)
        except TypeError:
            logger.error('Generator plugin does not support NeUploader')
            self.is_test_finished = lambda: -1
            self.reader = []

    @thread_safe_property
    def col_map(self):
        return {
            'interval_real': self.data_session.new_true_metric,
            'connect_time': self.data_session.new_true_metric,
            'send_time': self.data_session.new_true_metric,
            'latency': self.data_session.new_true_metric,
            'receive_time': self.data_session.new_true_metric,
            'interval_event': self.data_session.new_true_metric,
            'net_code': self.data_session.new_event_metric,
            'proto_code': self.data_session.new_event_metric
        }

    @thread_safe_property
    def data_session(self):
        """
        :rtype: DataSession
        """
        if self._data_session is None:
            self._data_session = DataSession({'clients': self.clients_cfg},
                                             test_start=self.core.status['generator']['test_start'] * 10**6)
            self.add_cleanup(self._cleanup)
            self._data_session.update_job(dict({'name': self.cfg.get('test_name'),
                                                '__type': 'tank'},
                                               **self.cfg.get('meta', {})))
        return self._data_session

    def _cleanup(self):
        uploader_metainfo = self.map_uploader_tags(self.core.status.get('uploader'))
        if self.core.status.get('autostop'):
            autostop_rps = self.core.status.get('autostop', {}).get('rps', 0)
            autostop_reason = self.core.status.get('autostop', {}).get('reason', '')
            self.log.warning('Autostop: %s %s', autostop_rps, autostop_reason)
            uploader_metainfo.update({'autostop_rps': autostop_rps, 'autostop_reason': autostop_reason})
        uploader_metainfo.update(self.cfg.get('meta', {}))
        self.data_session.update_job(uploader_metainfo)
        self.data_session.close(test_end=self.core.status.get('generator', {}).get('test_end', 0) * 10**6)

    def is_test_finished(self):
        df = next(self.reader)
        if df is not None:
            self.upload(df)
        return -1

    def monitoring_data(self, data_list):
        self.upload_monitoring(data_list)

    def post_process(self, retcode):
        try:
            for chunk in self.reader:
                if chunk is not None:
                    self.upload(chunk)
        except KeyboardInterrupt:
            logger.warning('Caught KeyboardInterrupt on Neuploader')
            self._cleanup()
        return retcode

    @property
    def is_telegraf(self):
        return True

    def get_metric_obj(self, col, case):
        """
        Generator of metric objects:
        Checks existent metrics and creates new metric if it does not exist.
        :param col:  str with column name
        :param case: str with case name
        :return: metric object
        """

        case_metrics = self.metrics_objs.get(case)
        if case_metrics is None:
            for col, constructor in self.col_map.items():
                # args = dict(self.cfg.get('meta', {}),
                #             name=col,
                #             case=case,
                #             raw=False,
                #             aggregate=True,
                #             source='tank',
                #             importance='high' if col in self.importance_high else '',
                #             )
                # if case != self.OVERALL:
                #     args.update(parent=self.get_metric_obj(col, self.OVERALL))
                self.metrics_objs.setdefault(case, {})[col] = constructor(
                    dict(self.cfg.get('meta', {}),
                         name=col,
                         source='tank',
                         importance='high' if col in self.importance_high else ''),
                    raw=False, aggregate=True,
                    parent=self.get_metric_obj(col, self.OVERALL) if case != self.OVERALL else None,
                    case=case if case != self.OVERALL else None
                )
        return self.metrics_objs[case][col]

    def upload(self, df):
        df_cases_set = set()
        for row in df.itertuples():
            if row.tag and isinstance(row.tag, str):
                df_cases_set.add(row.tag)
                if '|' in row.tag:
                    for tag in row.tag.split('|'):
                        df_cases_set.add(tag)

        for column in self.col_map:
            overall_metric_obj = self.get_metric_obj(column, self.OVERALL)
            df['value'] = df[column]
            result_df = self.filter_df_by_case(df, self.OVERALL)
            overall_metric_obj.put(result_df)

            for case_name in df_cases_set:
                case_metric_obj = self.get_metric_obj(column, case_name)
                df['value'] = df[column]
                result_df = self.filter_df_by_case(df, case_name)
                case_metric_obj.put(result_df)

    def upload_monitoring(self, data):
        for metric_name, df in self.monitoring_data_to_dfs(data).items():
            if metric_name not in self.monitoring_metrics:
                panel, metric = metric_name.split(':', 1)
                try:
                    group, name = metric.split('_', 1)
                except ValueError:
                    name = metric
                    group = '_OTHER_'
                self.monitoring_metrics[metric_name] = self.data_session.new_true_metric(name,
                                                                                         group=group,
                                                                                         host=panel,
                                                                                         type='monitoring',
                                                                                         **self.cfg.get('meta', {}))
            self.monitoring_metrics[metric_name].put(df)

    @staticmethod
    def monitoring_data_to_dfs(data):
        panels = {}
        for chunk in data:
            for panel_name, content in chunk['data'].items():
                if panel_name in panels:
                    for metric_name, value in content['metrics'].items():
                        if metric_name in panels[panel_name]:
                            panels[panel_name][metric_name]['value'].append(value)
                            panels[panel_name][metric_name]['ts'].append(chunk['timestamp'])
                        else:
                            panels[panel_name][metric_name] = {'value': [value], 'ts': [chunk['timestamp']]}
                else:
                    panels[panel_name] = {name: {'value': [value], 'ts': [chunk['timestamp']]} for name, value in content['metrics'].items()}
        return {'{}:{}'.format(panelk, name): pandas.DataFrame({'ts': [ts * 1000000 for ts in values['ts']], 'value': values['value']})
                for panelk, panelv in panels.items() for name, values in panelv.items()}

    @staticmethod
    def filter_df_by_case(df, case):
        """
        Filter dataframe by case name. If case is '__overall__', return all rows.
        :param df: DataFrame
        :param case: str with case name
        :return: DataFrame with columns 'ts' and 'value'
        """
        case = case.strip()
        return df[['ts', 'value']] if case == Plugin.OVERALL else df[df.tag.str.strip() == case][['ts', 'value']]

    def map_uploader_tags(self, uploader_tags):
        if not uploader_tags:
            logger.info('No uploader metainfo found')
            return {}
        else:
            meta_tags_names = ['component', 'description', 'name', 'person', 'task', 'version', 'lunapark_jobno']
            meta_tags = {key: uploader_tags.get(key) for key in meta_tags_names if key in uploader_tags}
            meta_tags.update({k: v if v is not None else '' for k, v in uploader_tags.get('meta', {}).items()})
            return meta_tags
