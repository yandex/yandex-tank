import json
import os
import sys
import time
import datetime
import string

from yandextank.plugins.Aggregator import AbstractReader


class PandoraReader(AbstractReader):

    """     Adapter to read phout files    """

    def __init__(self, owner, phantom):
        AbstractReader.__init__(self, owner)
        self.phantom = phantom
        self.phout_file = None
        self.phout = None
        self.stat = None
        self.stat_data = {}
        self.steps = []
        self.first_request_time = sys.maxint
        self.partial_buffer = ''
        self.stat_read_buffer = ''
        self.pending_second_data_queue = []
        self.last_sample_time = 0
        self.read_lines_count = 0
        self.buffered_seconds = 3
        self.enum_ammo = self.phantom.enum_ammo

    def check_open_files(self):
        info = self.phantom.get_info()
        if not self.phout and os.path.exists(self.phout_file):
            self.log.debug("Opening phout file: %s", self.phout_file)
            self.phout = open(self.phout_file, 'r')
            if info:
                self.steps = info.steps

        if not self.stat and info and os.path.exists(info.stat_log):
            self.log.debug(
                "Opening stat file: %s", self.phantom.phantom.stat_log)
            self.stat = open(self.phantom.phantom.stat_log, 'r')

    def close_files(self):
        if self.stat:
            self.stat.close()

        if self.phout:
            self.phout.close()

    def get_next_sample(self, force):
        if self.stat and len(self.data_queue) < self.buffered_seconds * 2:
            self.__read_stat_data()
        return self.__read_phout_data(force)

    def __read_stat_data(self):
        """ Read active instances info """
        end_marker = "\n},"
        self.stat_read_buffer += self.stat.read()
        while end_marker in self.stat_read_buffer:
            chunk_str = self.stat_read_buffer[
                :self.stat_read_buffer.find(end_marker) + len(end_marker) - 1]
            self.stat_read_buffer = self.stat_read_buffer[
                self.stat_read_buffer.find(end_marker) + len(end_marker) + 1:]
            chunk = json.loads("{%s}" % chunk_str)
            self.log.debug(
                "Stat chunk (left %s bytes): %s",
                len(self.stat_read_buffer), chunk)

            for date_str in chunk.keys():
                statistics = chunk[date_str]

                date_obj = datetime.datetime.strptime(
                    date_str.split(".")[0], '%Y-%m-%d %H:%M:%S')
                pending_datetime = int(time.mktime(date_obj.timetuple()))
                self.stat_data[pending_datetime] = 0

                for benchmark_name in statistics.keys():
                    if not benchmark_name.startswith("benchmark_io"):
                        continue
                    benchmark = statistics[benchmark_name]
                    for method in benchmark:
                        meth_obj = benchmark[method]
                        if "mmtasks" in meth_obj:
                            self.stat_data[
                                pending_datetime] += meth_obj["mmtasks"][2]
                self.log.debug(
                    "Active instances: %s=>%s",
                    pending_datetime, self.stat_data[pending_datetime])

        self.log.debug(
            "Instances info buffer size: %s / Read buffer size: %s",
            len(self.stat_data),
            len(self.stat_read_buffer))

    def __read_phout_data(self, force):
        """         Read phantom results        """
        if self.phout and len(self.data_queue) < self.buffered_seconds * 2:
            self.log.debug("Reading phout, up to 10MB...")
            first_line = self.phout.readline()
            phout = self.phout.readlines(10 * 1024 * 1024)
            if first_line:
                phout = [first_line] + phout
        else:
            self.log.debug("Skipped phout reading")
            phout = []

        self.log.debug("About to process %s phout lines", len(phout))
        time_before = time.time()
        for line in phout:
            line = self.partial_buffer + line
            self.partial_buffer = ''
            if line[-1] != "\n":
                self.log.debug("Not complete line, buffering it: %s", line)
                self.partial_buffer = line
                continue

            # 1346949510.514        74420    66    78    65409    8867    74201    18    15662    0    200
            # self.log.debug("Phout line: %s", line)
            self.read_lines_count += 1
            data = line[:-1].split("\t")

            if len(data) != 12:
                self.log.warning("Wrong phout line, skipped: %s", line)
                continue
            rt_real = int(data[2])
            tstmp = float(data[0])
            cur_time = int(tstmp + float(rt_real) / 1000000)

            if cur_time in self.stat_data.keys():
                active = self.stat_data[cur_time]
            else:
                active = 0

            if not cur_time in self.data_queue:
                self.first_request_time = min(
                    self.first_request_time, int(tstmp))
                if self.data_queue and self.data_queue[-1] >= cur_time:
                    self.log.warning(
                        "Aggregator data dates must be sequential: %s vs %s",
                        cur_time, self.data_queue[-1])
                    cur_time = self.data_queue[-1]
                else:
                    self.data_queue.append(cur_time)
                    self.data_buffer[cur_time] = []

            # marker, threads, overallRT, httpCode, netCode
            # bytes:     sent    received
            # connect    send    latency    receive
            #        accuracy
            marker = data[1]
            if self.enum_ammo:
                marker = string.rsplit(marker, "#", 1)[0]
            data_item = (marker, active, rt_real / 1000, data[11], data[10],
                         int(data[8]), int(data[9]),
                         int(data[3]) / 1000, int(data[4]) / 1000,
                         int(data[5]) / 1000, int(data[6]) / 1000,
                         (float(data[7]) + 1) / (rt_real + 1))

            self.data_buffer[cur_time].append(data_item)

        spent = time.time() - time_before
        if spent:
            self.log.debug(
                "Parsing speed: %s lines/sec", int(len(phout) / spent))
        self.log.debug("Read lines total: %s", self.read_lines_count)
        self.log.debug("Seconds queue: %s", self.data_queue)
        self.log.debug("Seconds buffer (up to %s): %s",
                       self.buffered_seconds, self.data_buffer.keys())
        if len(self.data_queue) > self.buffered_seconds:
            self.log.debug("Should send!")
            return self.pop_second()

        if self.pending_second_data_queue:
            return self.__process_pending_second()

        if force and self.data_queue:
            return self.pop_second()
        else:
            self.log.debug("No queue data!")
            return None

    def __aggregate_next_second(self):
        """ calls aggregator if there is data """
        parsed_sec = AbstractReader.pop_second(self)
        if parsed_sec:
            timestamp = int(time.mktime(parsed_sec.time.timetuple()))
            if timestamp in self.stat_data.keys():
                parsed_sec.overall.active_threads = self.stat_data[timestamp]
                for marker in parsed_sec.cases:
                    parsed_sec.cases[
                        marker].active_threads = self.stat_data[timestamp]
                del self.stat_data[timestamp]
            self.pending_second_data_queue.append(parsed_sec)
        else:
            self.log.debug("No new seconds present")

    def __process_pending_second(self):
        """ process data in queue """
        next_time = int(
            time.mktime(self.pending_second_data_queue[0].time.timetuple()))
        if self.last_sample_time and (next_time - self.last_sample_time) > 1:
            self.last_sample_time += 1
            self.log.debug(
                "Adding phantom zero sample: %s", self.last_sample_time)
            res = self.get_zero_sample(
                datetime.datetime.fromtimestamp(self.last_sample_time))
        else:
            res = self.pending_second_data_queue.pop(0)
        self.last_sample_time = int(time.mktime(res.time.timetuple()))
        res.overall.planned_requests = self.__get_expected_rps()
        self.log.debug("Pop result: %s", res)
        return res

    def pop_second(self):
        self.__aggregate_next_second()

        if not self.pending_second_data_queue:
            self.log.debug("pending_second_data_queue empty")
            return None
        else:
            self.log.debug(
                "pending_second_data_queue: %s", self.pending_second_data_queue)
            res = self.__process_pending_second()
            return res

    def __get_expected_rps(self):
        """
        Mark second with expected rps
        """
        while self.steps and self.steps[0][1] < 1:
            self.steps.pop(0)

        if not self.steps:
            return 0
        else:
            self.steps[0][1] -= 1
            return self.steps[0][0]
