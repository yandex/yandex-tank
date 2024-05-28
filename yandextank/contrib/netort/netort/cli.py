from __future__ import print_function

import argparse

from datetime import datetime

import signal
from yandextank.contrib.netort.netort.data_manager import DataSession
import pandas as pd
import logging

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)


def string_to_df_microsec(data):
    # start_time = time.time()
    try:
        df = pd.read_csv(
            StringIO(data), sep='\t', names=phout_columns, na_values='', dtype=dtypes, quoting=QUOTE_NONE  # noqa
        )
    except CParserError as e:  # noqa
        logger.error(e.message)  # noqa
        logger.error('Incorrect phout data: {}'.format(data))  # noqa
        return

    df['ts'] = (df['send_ts'] * 1e6 + df['interval_real']).astype(int)
    df['tag'] = df.tag.str.rsplit('#', 1, expand=True)[0]
    # logger.debug("Chunk decode time: %.2fms", (time.time() - start_time) * 1000)
    return df


def get_handler(data_session):
    def handler(signum, frame):
        data_session.interrupt()
    return handler


def get_uploader(data_session, column_mapping, overall_only=False):
    """
    :type data_session: DataSession
    """
    _router = {}
    _overall = {
        'interval_real': data_session.new_true_metric('interval_real overall', raw=False, aggregate=True, source='tank'),
        'connect_time': data_session.new_true_metric('connect_time overall', raw=False, aggregate=True, source='tank'),
        'send_time': data_session.new_true_metric('send_time overall', raw=False, aggregate=True, source='tank'),
        'latency': data_session.new_true_metric('latency overall', raw=False, aggregate=True, source='tank'),
        'receive_time': data_session.new_true_metric('receive_time overall', raw=False, aggregate=True, source='tank'),
        'interval_event': data_session.new_true_metric('interval_event overall', raw=False, aggregate=True, source='tank'),
        'net_code': data_session.new_event_metric('net_code overall', raw=False, aggregate=True, source='tank'),
        'proto_code': data_session.new_event_metric('proto_code overall', raw=False, aggregate=True, source='tank')}

    def get_router(tags):
        """
        :param tags:
        :return: {'%tag': {'%column_name': metric_object(name, group)}}
        """
        if set(tags) - set(_router.keys()):
            [_router.setdefault(tag,
                                {col_name: data_session.new_true_metric(name + '-' + tag,
                                                                        raw=False,
                                                                        aggregate=True)
                                 for col_name, name in column_mapping.items()} if not overall_only else {}
                                )
             for tag in tags]
        return _router

    def upload_overall(df):
        for col_name, metric in _overall.items():
            df['value'] = df[col_name]
            metric.put(df)

    def upload_df(df):
        router = get_router(df.tag.unique().tolist())
        if len(router) > 0:
            for tag, df_tagged in df.groupby('tag'):
                for col_name, metric in router[tag].items():
                    df_tagged['value'] = df_tagged[col_name]
                    metric.put(df_tagged)
        upload_overall(df)

    return upload_overall if overall_only else upload_df


def main():
    parser = argparse.ArgumentParser(description='Process phantom output.')
    parser.add_argument('phout', type=str, help='path to phantom output file')
    parser.add_argument('--url', type=str, default='https://test-back.luna.yandex-team.ru/')
    parser.add_argument('--name', type=str, help='test name', default=str(datetime.utcnow()))
    parser.add_argument('--db_name', type=str, help='ClickHouse database name', default='luna_test')
    args = parser.parse_args()

    clients = [
        {'type': 'luna', 'api_address': args.url, 'db_name': args.db_name},
        {'type': 'local_storage'}
    ]
    data_session = DataSession({'clients': clients})
    data_session.update_job({'name': args.name})
    print('Test name: %s' % args.name)

    col_map_aggr = {name: 'metric %s' % name for name in
                    ['interval_real', 'connect_time', 'send_time', 'latency',
                     'receive_time', 'interval_event']}
    uploader = get_uploader(data_session, col_map_aggr, True)

    signal.signal(signal.SIGINT, get_handler(data_session))

    with open(args.phout) as f:
        buffer = ''
        while True:
            parts = f.read(128*1024)
            try:
                chunk, new_buffer = parts.rsplit('\n', 1)
                chunk = buffer + chunk + '\n'
                buffer = new_buffer
            except ValueError:
                chunk = buffer + parts
                buffer = ''
            if len(chunk) > 0:
                df = string_to_df_microsec(chunk)
                uploader(df)
            else:
                break
    data_session.close()


if __name__ == '__main__':
    main()
