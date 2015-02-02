""" Core module to calculate aggregate data """
import copy
import datetime
import logging
import math
import time

from yandextank.core import AbstractPlugin
import yandextank.core as tankcore


class AggregateResultListener:
    """ listener to be notified about aggregate data """

    def __init__(self):
        pass

    def aggregate_second(self, second_aggregate_data):
        """ notification about new aggregate data """
        raise NotImplementedError("Abstract method needs to be overridden")


class AggregatorPlugin(AbstractPlugin):
    """ Plugin that manages aggregation """
    default_time_periods = "1ms 2 3 4 5 6 7 8 9 10 20 30 40 50 60 70 80 90 100 " \
                           "150 200 250 300 350 400 450 500 600 650 700 750 800 850 900 950 1s " \
                           "1500 2s 2500 3s 3500 4s 4500 5s 5500 6s 6500 7s 7500 8s 8500 9s 9500 10s 11s"

    SECTION = 'aggregator'

    @staticmethod
    def get_key():
        return __file__

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.process = None
        self.second_data_listeners = []
        self.preproc_out_offset = 0
        self.buffer = []
        self.second_data_draft = []
        self.preproc_out_filename = None
        self.cumulative_data = SecondAggregateDataTotalItem()
        self.reader = None
        self.time_periods = [tankcore.expand_to_milliseconds(x)
                             for x in self.default_time_periods.split(' ')]
        self.last_sample_time = 0
        self.precise_cumulative = 1

    def get_available_options(self):
        return ["time_periods", "precise_cumulative"]

    def configure(self):
        periods = self.get_option(
            "time_periods", self.default_time_periods).split(" ")
        self.time_periods = [
            tankcore.expand_to_milliseconds(x) for x in periods]
        self.core.set_option(
            self.SECTION, "time_periods", " ".join([str(x) for x in periods]))
        self.precise_cumulative = int(
            self.get_option("precise_cumulative", '1'))

    def start_test(self):
        if not self.reader:
            self.log.warning("No one had set reader for aggregate data yet...")

    def is_test_finished(self):
        # read up to 2 samples in single pass
        self.__read_samples(2)
        return -1

    def end_test(self, retcode):
        self.__read_samples(force=True)
        if self.reader:
            self.reader.close_files()
        return retcode

    def add_result_listener(self, listener):
        """ add object to data listeners """
        self.second_data_listeners.append(listener)

    def __notify_listeners(self, data):
        """ notify all listeners about aggregate data """
        self.log.debug(
            "Notifying listeners about second: %s , %s/%s req/responses",
            data.time, data.overall.planned_requests, data.overall.RPS)
        for listener in self.second_data_listeners:
            listener.aggregate_second(data)

    def get_timeout(self):
        """ get timeout based on time_periods last val """
        return self.time_periods[-1:][0]

    def __generate_zero_samples(self, data):
        """ fill timeline gaps with zero samples """
        if not data:
            return
        while self.last_sample_time and int(time.mktime(data.time.timetuple())) - self.last_sample_time > 1:
            self.last_sample_time += 1
            self.log.warning("Adding zero sample: %s", self.last_sample_time)
            zero = self.reader.get_zero_sample(
                datetime.datetime.fromtimestamp(self.last_sample_time))
            self.__notify_listeners(zero)
        self.last_sample_time = int(time.mktime(data.time.timetuple()))

    def __read_samples(self, limit=0, force=False):
        """ call reader object to read next sample set """
        if self.reader:
            self.reader.check_open_files()
            data = self.reader.get_next_sample(force)
            count = 0
            while data:
                self.last_sample_time = int(time.mktime(data.time.timetuple()))
                self.__generate_zero_samples(data)
                self.__notify_listeners(data)
                if limit < 1 or count < limit:
                    data = self.reader.get_next_sample(force)
                else:
                    data = None
                count += 1


# ===============================================================
class SecondAggregateData:
    """ class holds aggregate data for the second """

    def __init__(self, cumulative_item=None):
        self.cases = {}
        self.time = None
        self.overall = SecondAggregateDataItem()
        self.cumulative = cumulative_item

    def __repr__(self):
        return "SecondAggregateData[%s][%s]" % (self.time, time.mktime(self.time.timetuple()))

    def __getstate__(self):
        return {
            'cases': self.cases,
            'overall': self.overall,
            'cumulative': self.cumulative,
        }


class SecondAggregateDataItem:
    """ overall and case items has this type """
    QUANTILES = [0.25, 0.50, 0.75, 0.80, 0.85, 0.90, 0.95, 0.98, 0.99, 1.00]

    def __init__(self):
        self.case = None
        self.planned_requests = 0
        self.active_threads = 0
        self.selfload = 0
        self.RPS = 0
        self.http_codes = {}
        self.net_codes = {}
        self.times_dist = []
        self.quantiles = {}
        self.dispersion = 0
        self.input = 0
        self.output = 0
        self.avg_connect_time = 0
        self.avg_send_time = 0
        self.avg_latency = 0
        self.avg_receive_time = 0
        self.avg_response_time = 0

    def __getstate__(self):
        return {
            # "case": self.case,
            "planned_requests": self.planned_requests,
            "active_threads": self.active_threads,
            # "selfload": self.selfload,
            "RPS": self.RPS,
            "http_codes": self.http_codes,
            "net_codes": self.net_codes,
            # "times_dist": self.times_dist,
            "quantiles": self.quantiles,
            # "dispersion": self.dispersion,
            # "input": self.input,
            # "output": self.output,
            # "avg_connect_time": self.avg_connect_time,
            # "avg_send_time": self.avg_send_time,
            # "avg_latency": self.avg_latency,
            # "avg_receive_time": self.avg_receive_time,
            # "avg_response_time": self.avg_response_time,
        }

class SecondAggregateDataTotalItem:
    """ total cumulative data item """

    def __init__(self):
        self.avg_connect_time = 0
        self.avg_send_time = 0
        self.avg_latency = 0
        self.avg_receive_time = 0
        self.avg_response_time = 0
        self.total_count = 0
        self.times_dist = {}
        self.quantiles = {}

    def __getstate__(self):
        return {
            # "avg_connect_time": self.avg_connect_time,
            # "avg_send_time": self.avg_send_time,
            # "avg_latency": self.avg_latency,
            # "avg_receive_time": self.avg_receive_time,
            # "avg_response_time": self.avg_response_time,
            "total_count": self.total_count,
            #"times_dist": self.times_dist,
            "quantiles": self.quantiles,
        }

    def add_data(self, overall_item):
        """ add data to total """
        for time_item in overall_item.times_dist:
            self.total_count += time_item['count']
            timing = int(time_item['from'])
            if timing in self.times_dist.keys():
                self.times_dist[timing]['count'] += time_item['count']
            else:
                self.times_dist[timing] = time_item

    def add_raw_data(self, times_dist):
        """ add data to total """
        for time_item in times_dist:
            self.total_count += 1
            timing = int(time_item)
            dist_item = self.times_dist.get(
                timing, {'from': timing, 'to': timing, 'count': 0})
            dist_item['count'] += 1
            self.times_dist[timing] = dist_item
        logging.debug("Total times len: %s", len(self.times_dist))

    def calculate_total_quantiles(self):
        """ calculate total quantiles based on times dist """
        self.quantiles = {}
        quantiles = reversed(copy.copy(SecondAggregateDataItem.QUANTILES))
        timings = sorted(self.times_dist.keys(), reverse=True)
        level = 1.0
        timing = 0
        for quan in quantiles:
            while level >= quan:
                timing = timings.pop(0)
                level -= float(
                    self.times_dist[timing]['count']) / self.total_count
            self.quantiles[quan * 100] = self.times_dist[timing]['to']

        logging.debug("Total quantiles: %s", self.quantiles)
        return self.quantiles


# ===============================================================

class AbstractReader:
    """
    Parent class for all source reading adapters
    """

    def __init__(self, owner):
        self.aggregator = owner
        self.log = logging.getLogger(__name__)
        self.cumulative = SecondAggregateDataTotalItem()
        self.data_queue = []
        self.data_buffer = {}

    def check_open_files(self):
        """ open files if necessary """
        pass

    def close_files(self):
        """        Close opened handlers to avoid fd leak        """
        pass

    def get_next_sample(self, force):
        """ read next sample from file """
        pass

    def parse_second(self, next_time, data):
        """ parse buffered data to aggregate item """
        self.log.debug("Parsing second: %s", next_time)
        result = self.get_zero_sample(
            datetime.datetime.fromtimestamp(next_time))
        time_before = time.time()
        for item in data:
            self.__append_sample(result.overall, item)
            marker = item[0]
            if marker:
                if not marker in result.cases.keys():
                    result.cases[marker] = SecondAggregateDataItem()
                self.__append_sample(result.cases[marker], item)

        # at this phase we have raw response times in result.overall.times_dist
        if self.aggregator.precise_cumulative:
            self.cumulative.add_raw_data(result.overall.times_dist)

        self.log.debug(
            "Calculate aggregates for %s requests", result.overall.RPS)
        self.__calculate_aggregates(result.overall)
        for case in result.cases.values():
            self.__calculate_aggregates(case)

        if not self.aggregator.precise_cumulative:
            self.cumulative.add_data(result.overall)
        self.cumulative.calculate_total_quantiles()

        spent = time.time() - time_before
        if spent:
            self.log.debug(
                "Aggregating speed: %s lines/sec", int(len(data) / spent))
        return result

    def __calculate_aggregates(self, item):
        """ calculate aggregates on raw data """
        if item.RPS:
            item.selfload = 100 * item.selfload / item.RPS
            item.avg_connect_time /= item.RPS
            item.avg_send_time /= item.RPS
            item.avg_latency /= item.RPS
            item.avg_receive_time /= item.RPS
            item.avg_response_time /= item.RPS

            item.times_dist.sort()
            count = 0.0
            quantiles = copy.copy(SecondAggregateDataItem.QUANTILES)
            times = copy.copy(self.aggregator.time_periods)
            time_from = 0
            time_to = times.pop(0)
            times_dist_draft = []
            times_dist_item = {'from': time_from, 'to': time_to, 'count': 0}
            deviation = 0.0
            timing = 0
            for timing in item.times_dist:
                count += 1
                if quantiles and (count / item.RPS) >= quantiles[0]:
                    level = quantiles.pop(0)
                    item.quantiles[level * 100] = timing

                while times and timing > time_to:
                    time_from = time_to
                    time_to = times.pop(0)
                    if times_dist_item['count']:
                        times_dist_draft.append(times_dist_item)
                    times_dist_item = {
                        'from': time_from, 'to': time_to, 'count': 0}

                times_dist_item['count'] += 1
                deviation += math.pow(item.avg_response_time - timing, 2)

            while quantiles:
                level = quantiles.pop(0)
                item.quantiles[level * 100] = timing

            if times_dist_item['count']:
                times_dist_draft.append(times_dist_item)

            item.dispersion = deviation / item.RPS
            item.times_dist = times_dist_draft

    def __append_sample(self, result, item):
        """ add single sample to aggregator buffer """
        for check in item:
            if check < 0:
                self.log.error("Problem item: %s", item)
                raise ValueError("One of the sample items has negative value")

        (marker, threads, overall_rt, http_code, net_code, sent_bytes,
         received_bytes, connect, send, latency, receive, accuracy) = item
        result.case = marker
        result.active_threads = threads
        result.planned_requests = 0
        result.RPS += 1

        if http_code and http_code != '0':
            if not http_code in result.http_codes.keys():
                result.http_codes[http_code] = 0
            result.http_codes[http_code] += 1
        if not net_code in result.net_codes.keys():
            result.net_codes[net_code] = 0
        result.net_codes[net_code] += 1

        result.input += received_bytes
        result.output += sent_bytes

        result.avg_connect_time += connect
        result.avg_send_time += send
        result.avg_latency += latency
        result.avg_receive_time += receive
        result.avg_response_time += overall_rt
        result.selfload += accuracy

        result.times_dist.append(overall_rt)

    def get_zero_sample(self, date_time):
        """ instantiate new aggregate data item """
        res = SecondAggregateData(self.cumulative)
        res.time = date_time
        return res

    def pop_second(self):
        """ pop from out queue new aggregate data item """
        self.data_queue.sort()
        next_time = self.data_queue.pop(0)
        data = self.data_buffer[next_time]
        del self.data_buffer[next_time]
        res = self.parse_second(next_time, data)
        return res
