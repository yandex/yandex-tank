# TODO: make the next two lines unnecessary
# pylint: disable=line-too-long
# pylint: disable=missing-docstring
import json
import logging
import os
import sys
import pandas as pd
from datetime import timedelta, datetime

import io

from collections import defaultdict
from ...common.interfaces import AbstractPlugin, AggregateResultListener

logger = logging.getLogger(__name__)  # pylint: disable=C0103


def calc_overall_times(overall, quantiles):
    cumulative = overall.cumsum()
    total = cumulative.max()
    positions = cumulative.searchsorted([float(i) / 100 * total for i in quantiles])
    all_times = [cumulative.index[i] / 1000. for i in positions]
    overall_times = zip(quantiles, all_times)
    return overall_times


def calc_duration(first_ts, last_ts):
    first_time = timedelta(seconds=first_ts)
    last_time = timedelta(seconds=last_ts)
    return str(last_time - first_time + timedelta(seconds=1))


def make_resp_json(overall_times, overall_proto_code, overall_net_code, duration, loadscheme, time_start,
                   autostop_info):
    quant = {}
    for q, t in overall_times:
        quant['q' + str(q)] = t
    res = {
        "duration": duration,
        "time_start": time_start,
        "loadscheme": loadscheme,
        "quantiles": quant,
        "proto_code": overall_proto_code,
        "net_code": overall_net_code
    }

    if autostop_info:
        res['autostop_rps'] = autostop_info['rps']
        res['autostop_reason'] = autostop_info['reason']

    try:
        response = json.dumps(res, indent=2, sort_keys=False)
    except ValueError as e:
        logger.warning('Can\'t convert offline report to json format: %s', e, exc_info=True)
        response = None
    return response


def make_resp_text(overall_times, overall_proto_code, overall_net_code, duration, loadscheme, time_start,
                   autostop_info):
    res = ['Duration: {:>8}\n'.format(duration)]
    res.append('Loadscheme: {}\n'.format(loadscheme))
    if autostop_info:
        res.append('Autostop rps: {}\n'.format(autostop_info['rps']))
        res.append('Autostop reason: {}\n'.format(autostop_info['reason']))
    res.append('Start time: {}\n'.format(time_start))
    res.append('Percentiles all ms:\n')
    for q, t in overall_times:
        res.append('{:>5}% < {:>5}\n'.format(q, t))
    res.append('HTTP codes(code/count):\n')
    for q, t in overall_proto_code.items():
        res.append('{:>5}: {:<7}\n'.format(q, t))
    res.append('Net codes(code/count):\n')
    for q, t in overall_net_code.items():
        res.append('{:>5}: {:<7}\n'.format(q, t))
    return ''.join(res)


class Plugin(AbstractPlugin, AggregateResultListener):
    # pylint:disable=R0902
    SECTION = 'offline_report'

    def __init__(self, core, cfg, name):
        super(Plugin, self).__init__(core, cfg, name)
        try:
            self.data_and_stats_stream = io.open(os.path.join(self.core.artifacts_dir,
                                                              self.get_option('offline_data_log')),
                                                 mode='w')
            self.add_cleanup(lambda: self.data_and_stats_stream.close())
            self.overall_json_stream = io.open(os.path.join(self.core.artifacts_dir,
                                                            self.get_option('offline_json_report')),
                                               mode='w')
            self.add_cleanup(lambda: self.overall_json_stream.close())
            self.overall_text_stream = io.open(os.path.join(self.core.artifacts_dir,
                                                            self.get_option('offline_text_report')),
                                               mode='w')
            self.add_cleanup(lambda: self.overall_text_stream.close())
        except Exception:
            logging.exception('Failed to open file', exc_info=True)
            raise OSError('Error opening OfflineReport log file')

        self.overall = None
        self.overall_proto_code = defaultdict(int)
        self.overall_net_code = defaultdict(int)
        self.quantiles = [10, 20, 30, 40, 50, 60, 70, 75, 80, 85, 90, 95, 99, 99.5, 100]
        self.print_report = self.get_option("print_report")
        self.first_ts = None
        self.last_ts = None
        self.stats = None

    def get_available_options(self):
        return ['offline_data_log', 'offline_json_report', 'offline_text_report', 'print_report']

    def configure(self):
        self.core.job.subscribe_plugin(self)

    def prepare_test(self):
        self.data_and_stats_stream.write('[')

    def on_aggregated_data(self, data, stats):
        """
        @data: aggregated data
        @stats: stats about gun
        """

        last_proto_code = data['overall']['proto_code']['count']
        for code, count in last_proto_code.items():
            self.overall_proto_code[code] += count

        last_net_code = data['overall']['net_code']['count']
        for code, count in last_net_code.items():
            self.overall_net_code[code] += count

        self.data_and_stats_stream.write(
            '%s,\n' % json.dumps({
                'ts': stats['ts'],
                'instances': stats['metrics']['instances'],
                'reqps': stats['metrics']['reqps'],
                'quantiles': {
                    "q50": int(data['overall']['interval_real']['q']['value'][0]),
                    "q75": int(data['overall']['interval_real']['q']['value'][1]),
                    "q80": int(data['overall']['interval_real']['q']['value'][2]),
                    "q85": int(data['overall']['interval_real']['q']['value'][3]),
                    "q90": int(data['overall']['interval_real']['q']['value'][4]),
                    "q95": int(data['overall']['interval_real']['q']['value'][5]),
                    "q98": int(data['overall']['interval_real']['q']['value'][6]),
                    "q99": int(data['overall']['interval_real']['q']['value'][7]),
                    "q100": int(data['overall']['interval_real']['q']['value'][8]),
                },
                'proto_code': last_proto_code,
                'net_code': data['overall']['net_code']['count']
            }))

        incoming_hist = data['overall']['interval_real']['hist']
        dist = pd.Series(incoming_hist['data'], index=incoming_hist['bins'])
        if self.overall is None:
            self.overall = dist
        else:
            self.overall = self.overall.add(dist, fill_value=0)

        if self.first_ts is None:
            self.first_ts = stats['ts']
        else:
            self.last_ts = stats['ts']

    def post_process(self, retcode):
        try:
            self.data_and_stats_stream.seek(self.data_and_stats_stream.tell() - 2, os.SEEK_SET)
            self.data_and_stats_stream.write(']')
        except ValueError as e:
            logger.error('Can\'t write offline report %s', e)

        overall_times = calc_overall_times(self.overall, self.quantiles)
        stepper_info = self.core.info.get_value(['stepper'])

        try:
            duration = str(timedelta(seconds=stepper_info['duration']))
        except (KeyError, TypeError) as e:
            logger.error('Can\'t get test duration %s', e)
            duration = calc_duration(self.first_ts, self.last_ts)

        try:
            loadscheme = ' '.join(stepper_info['loadscheme'])
        except (KeyError, TypeError) as e:
            logger.error('Can\'t get test loadscheme %s', e)
            loadscheme = None

        generator_info = self.core.info.get_value(['generator'])
        try:
            time_start = datetime.fromtimestamp(generator_info['time_start']).strftime("%Y-%m-%d %H:%M:%S")
        except (KeyError, TypeError) as e:
            logger.error('Can\'t get test start time %s', e)
            time_start = datetime.fromtimestamp(self.first_ts).strftime("%Y-%m-%d %H:%M:%S")

        try:
            autostop_info = self.core.info.get_value(['autostop'])
        except (KeyError, TypeError) as e:
            logger.error('Can\'t get autostop info %s', e)
            autostop_info = None

        resp_json = make_resp_json(
            overall_times,
            self.overall_proto_code,
            self.overall_net_code,
            duration,
            loadscheme,
            time_start,
            autostop_info
        )
        if resp_json is not None:
            self.overall_json_stream.write('%s' % resp_json)

        resp_text = make_resp_text(
            overall_times,
            self.overall_proto_code,
            self.overall_net_code,
            duration,
            loadscheme,
            time_start,
            autostop_info
        )
        self.overall_text_stream.write('%s' % resp_text)

        if self.print_report:
            sys.stdout.write(resp_text)

        return retcode
