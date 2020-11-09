import logging

from urllib.parse import urljoin

import re
import pandas
import requests
from netort.data_manager import DataSession, thread_safe_property
import threading as th
from requests import ConnectionError

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
    LUNA_LINK = 'https://luna.yandex-team.ru/tests/'
    PLANNED_RPS_METRICS_NAME = 'planned_rps'
    ACTUAL_RPS_METRICS_NAME = 'actual_rps'

    def __init__(self, core, cfg, name):
        super(Plugin, self).__init__(core, cfg, name)
        self.clients_cfg = [{'type': 'luna',
                             'api_address': self.cfg.get('api_address'),
                             'db_name': self.cfg.get('db_name'),
                             'max_df_len': self.cfg.get('max_df_len')}]
        self.metrics_objs = {}  # map of case names and metric objects
        self.monitoring_metrics = {}
        self.rps_metrics = {
            'actual_rps_metrics_obj': None,
            'planned_rps_metrics_obj': None,
            'actual_rps_latest': pandas.Series([])
        }
        self.rps_uploader = th.Thread(target=self.upload_planned_rps)

        self._col_map = None
        self._data_session = None
        self._meta = None
        self._test_name = None

    @property
    def meta(self):
        if self._meta is None:
            self._meta = dict(self.get_lp_meta(), **self.cfg.get('meta', {}))
        return self._meta

    @property
    def test_name(self):
        if self._test_name is None:
            self._test_name = self.cfg.get('test_name') or self.core.info.get_value(['uploader', 'job_name'])
        return self._test_name

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
            config_filenames = {'validated_conf.yaml', 'configinitial.yaml'}
            self._data_session = DataSession({'clients': self.clients_cfg},
                                             tankapi_info=self.tankapi_info(),
                                             config_filenames=config_filenames,
                                             artifacts_dir=self.core.artifacts_dir,
                                             test_start=self.core.info.get_value(['generator', 'test_start'], 0) * 10**6)
            self.add_cleanup(self._cleanup)
            self._data_session.update_job(dict({'name': self.test_name,
                                                '__type': 'tank'},
                                               **self.meta))
            job_no = self._data_session.clients[0].job_number
            if job_no:
                self.publish('job_no', int(job_no))
                self.publish('web_link', urljoin(self.LUNA_LINK, job_no))
        return self._data_session

    def tankapi_info(self):
        meta = self.cfg.get('meta', {})
        return {
            'host': meta.get('tankapi_host'),
            'port': meta.get('tankapi_port'),
            'local_id': self.core.test_id
        }

    def _cleanup(self):
        self.upload_actual_rps(data=pandas.DataFrame([]), last_piece=True)
        uploader_metainfo = self.get_lp_meta()
        autostop_info = self.get_autostop_info()
        regressions = self.get_regressions_names(uploader_metainfo)
        lp_link = self.core.info.get_value(['uploader', 'web_link'])

        meta = self.meta
        meta.update(autostop_info)
        meta['regression'] = regressions
        meta['lunapark_link'] = lp_link

        self.data_session.update_job(meta)
        self.data_session.close(test_end=self.core.info.get_value(['generator', 'test_end'], 0) * 10**6)

    def is_test_finished(self):
        df = next(self.reader)
        if df is not None:
            self.upload(df)
        return -1

    def monitoring_data(self, data_list):
        self.upload_monitoring(data_list)

    def post_process(self, retcode):
        try:
            self.rps_uploader.start()
            for chunk in self.reader:
                if chunk is not None:
                    self.upload(chunk)
            self.upload_actual_rps(data=pandas.DataFrame([]), last_piece=True)
            if self.rps_uploader.is_alive():
                self.rps_uploader.join()
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
                self.metrics_objs.setdefault(case, {})[col] = constructor(
                    dict(self.meta,
                         name=col,
                         source='tank',
                         importance='high' if col in self.importance_high else ''),
                    raw=False, aggregate=True,
                    parent=self.get_metric_obj(col, self.OVERALL) if case != self.OVERALL else None,
                    case=case if case != self.OVERALL else None
                )
        return self.metrics_objs[case][col]

    def upload(self, df):
        self.upload_actual_rps(df)

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
                self.monitoring_metrics[metric_name] =\
                    self.data_session.new_true_metric(
                        meta=dict(self.meta,
                                  name=name,
                                  group=group,
                                  host=panel,
                                  type='monitoring'))
            self.monitoring_metrics[metric_name].put(df)

    def upload_planned_rps(self):
        """ Uploads planned rps as a raw metric """
        df = self.parse_stpd()

        if not df.empty:
            self.rps_metrics['planned_rps_metrics_obj'] = self.data_session.new_true_metric(
                meta=dict(self.meta, name=self.PLANNED_RPS_METRICS_NAME, source='tank'),
                raw=True, aggregate=False, parent=None, case=None)
            self.rps_metrics['planned_rps_metrics_obj'].put(df)

    def upload_actual_rps(self, data, last_piece=False):
        """ Upload actual rps metric """
        if self.rps_metrics['actual_rps_metrics_obj'] is None:
            self.rps_metrics['actual_rps_metrics_obj'] = self.data_session.new_true_metric(
                meta=dict(self.meta, name=self.ACTUAL_RPS_METRICS_NAME),
                raw=True, aggregate=False, parent=None, case=None
            )
        df = self.count_actual_rps(data, last_piece)
        if not df.empty:
            self.rps_metrics['actual_rps_metrics_obj'].put(df)

    def parse_stpd(self):
        """  Reads rps plan from stpd file """
        stpd_file = self.core.info.get_value(['stepper', 'stpd_file'])
        if not stpd_file:
            logger.info('No stpd found, no planned_rps metrics')
            return pandas.DataFrame()

        rows_list = []
        test_start = int(self.core.info.get_value(['generator', 'test_start'], 0) * 10 ** 3)
        pattern = r'^\d+ (\d+)\s*.*$'
        regex = re.compile(pattern)
        try:
            with open(stpd_file) as stpd:
                for line in stpd:
                    if regex.match(line):
                        timestamp = int((int(line.split(' ')[1]) + test_start) / 1e3)  # seconds
                        rows_list.append(timestamp)
        except Exception:
            logger.warning('Failed to parse stpd file')
            logger.debug('', exc_info=True)
            return pandas.DataFrame()

        return self.rps_series_to_df(pandas.Series(rows_list))

    def count_actual_rps(self, data, last_piece):
        """ Counts actual rps on base of input chunk. Uses buffer for latest timestamp in df. """
        if not last_piece and not data.empty:
            concat_ts = pandas.concat([(data.ts / 1e6).astype(int), self.rps_metrics['actual_rps_latest']])
            self.rps_metrics['actual_rps_latest'] = concat_ts.loc[lambda s: s == concat_ts.max()]
            series_to_send = concat_ts.loc[lambda s: s < concat_ts.max()]
            df = self.rps_series_to_df(series_to_send) if series_to_send.any else pandas.DataFrame([])
        else:
            df = self.rps_series_to_df(self.rps_metrics['actual_rps_latest'])
            self.rps_metrics['actual_rps_latest'] = pandas.Series()
        return df

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
    def rps_series_to_df(series):
        df = series.value_counts().to_frame(name='value')
        df_to_send = df.rename_axis('ts')
        df_to_send.reset_index(inplace=True)
        df_to_send.loc[:, 'ts'] = (df_to_send['ts'] * 1e6).astype(int)
        return df_to_send

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

    def get_lp_meta(self):
        uploader_meta = self.core.info.get_value(['uploader'])
        if not uploader_meta:
            logger.info('No uploader metainfo found')
            return {}
        else:
            meta_tags_names = ['component', 'description', 'name', 'person', 'task', 'version', 'lunapark_jobno']
            meta_tags = {key: uploader_meta.get(key) for key in meta_tags_names if key in uploader_meta}
            meta_tags.update({k: v if v is not None else '' for k, v in uploader_meta.get('meta', {}).items()})
            return meta_tags

    @staticmethod
    def get_regressions_names(uploader_metainfo):
        task, component_name = uploader_metainfo.get('task'), uploader_metainfo.get('component')
        if not task or not component_name:
            return []
        project_name = task.split('-')[0]
        lp_api_url = 'https://lunapark.yandex-team.ru/api/regress/{}/componentlist.json'.format(project_name)
        try:
            componentlist =\
                requests.get(lp_api_url).json()
        except (ValueError, ConnectionError):
            logger.info("Failed to fetch data from {}".format(lp_api_url), exc_info=True)
            return []
        for component in componentlist:
            try:
                if component['name'] == component_name:
                    services = component['services']
                    if len(services) == 0:
                        services = ['__OTHER__']
                    return ['{}_{}'.format(project_name, s).replace(' ', '_') for s in services]
            except KeyError:
                pass
        else:
            return []

    def get_autostop_info(self):
        autostop_info = self.core.info.get_value(['autostop'])
        if autostop_info:
            autostop_rps = autostop_info.get('rps', 0)
            autostop_reason = autostop_info.get('reason', '')
            self.log.warning('Autostop: %s %s', autostop_rps, autostop_reason)
            return {'autostop_rps': autostop_rps, 'autostop_reason': autostop_reason}
        else:
            return {}
