from Tank.Core import AbstractPlugin
from Tank.Utils import CommonUtils
import datetime
import logging
import os
import shutil
import signal
import subprocess
import tempfile
import time

class AggregateResultListener:
    def aggregate_second(self, second_aggregate_data):
        raise TypeError("Abstract method needs to be overridden")
    

# TODO: rewrite it with python preproc object
class AggregatorPlugin(AbstractPlugin):

    default_time_periods = "1 2 3 4 5 6 7 8 9 10 20 30 40 50 60 70 80 90 100 150 200 250 300 350 400 450 500 600 650 700 750 800 850 900 950 1s 1500 2s 2500 3s 3500 4s 4500 5s 5500 6s 6500 7s 7500 8s 8500 9s 9500 10s 11s"

    OPTION_STEPS = 'steps'
    SECTION = 'aggregator'
    OPTION_CASES = 'cases'
    OPTION_SOURCE_FILE = "source_file"
    OPTION_STAT_FILE = "threads_file"
    OPTION_DETAILED_FIELD = "detailed_time"
    
    AB_TO_PHOUT_CONVERTER = "tail -n+2 | awk 'BEGIN {FS=\"\\t\"; OFS=\"\\t\"} {printf \"%7.3f\\t\\t%d\\t%d\\t%d\\t%d\\t%d\\t%d\\t%d\\t%d\\t%d\\t%d\\n\", $2/1, $5*1000, $3*1000, 0, $6*1000, ($5-$6)*1000, $5*1000, 0,0,0, 200}'"

    @staticmethod
    def get_key():
        return __file__
        
    def __init__(self, core):
        self.log = logging.getLogger(__name__)
        self.core = core
        self.process = None
        self.second_data_listeners = []
        self.preproc_out_offset = 0
        self.buffer = []
        self.second_data_draft = []
        self.preproc_out_filename = None
    
    def configure(self):
        self.tools_path = self.core.get_option(self.SECTION, "tools_path", '/usr/bin')
        self.phout_file = self.core.get_option(self.SECTION, self.OPTION_SOURCE_FILE, '')
        self.threads_file = self.core.get_option(self.SECTION, self.OPTION_STAT_FILE, '')
        periods = self.core.get_option(self.SECTION, "time_periods", self.default_time_periods).split(" ")
        self.time_periods = " ".join([ str(CommonUtils.expand_to_milliseconds(x)) for x in periods ])
        self.core.set_option(self.SECTION, "time_periods", self.time_periods)
#        self.tank_type = self.core.get_option(self.SECTION, "tank_type") 
        self.preproc_out_filename = self.core.get_option(self.SECTION, "preproc_log_name", tempfile.mkstemp(".log", "preproc_")[1])
        self.core.add_artifact_file(self.preproc_out_filename)
        self.preproc_cases = self.core.get_option(self.SECTION, self.OPTION_CASES, "")
        self.detailed_field = self.core.get_option(self.SECTION, self.OPTION_DETAILED_FIELD, 'interval_real')
        self.preproc_steps = self.core.get_option(self.SECTION, self.OPTION_STEPS, "")
        self.core.set_option(self.SECTION, self.OPTION_STEPS, self.preproc_steps)
        self.core.add_artifact_file(os.path.realpath("lunapark.log"))

    def prepare_test(self):
        pass
    
    def process_listeners_callback(self, draft_data):
        try:
            second_data = SecondAggregateData(draft_data)
        except RuntimeError, ex:
            self.log.error("Can't parse second data: %s", ex)
            return
        
        for listener in self.second_data_listeners:
            self.log.debug("Notifying second data listener: %s", listener)
            listener.aggregate_second(second_data)

    def read_preproc_lines(self, handle, callback):
        overall_flag = 0
        for line in handle:
            #self.log.debug("Preproc Line: %s", line)
            self.buffer += [line]
            if line.startswith(SecondAggregateDataItem.T_OVERALL):
                overall_flag = int(line.strip()[-1:])
            if line.strip() == "===":
                self.apply_buffer_to_draft()
                if overall_flag:
                    callback(self.second_data_draft)
                    self.second_data_draft = []

    def start_test(self):
        if not self.phout_file:
            raise RuntimeError("No input file specified")
        if not self.preproc_out_filename:
            raise RuntimeError("No preproc out file specified")
        
        # wait for phout_file file to appear
        for retry in [1, 2, 3, 4, 5]:
            if not os.path.exists(self.phout_file):
                self.log.debug("Waiting for %s to appear", self.phout_file)
                time.sleep(retry)
        
        shutil.copy(self.core.config.file, 'lp.conf')
        self.core.add_artifact_file(os.path.realpath("lp.conf"))

        if self.threads_file:
            self.args = "perl -I " + self.tools_path + " -f " + self.tools_path + "/prd.pl " + self.phout_file
            if self.threads_file:
                self.args += " " + self.threads_file
        else:
            self.args = "tail -f " + self.phout_file + "|" + self.AB_TO_PHOUT_CONVERTER
                       
        self.args += "| perl -I " + self.tools_path + " -f " + self.tools_path + "/preproc.pl"

        self.log.debug("Starting: %s", self.args)
        self.process = subprocess.Popen(self.args, shell=True, preexec_fn=os.setsid) # setsid required for killpg

    def is_test_finished(self):
        self.log.debug("Reading preproc out lines at: %s [%s]", self.preproc_out_filename, self.preproc_out_offset)
        preproc_out_handle = open(self.preproc_out_filename, 'r')
        preproc_out_handle.seek(self.preproc_out_offset)        
        self.read_preproc_lines(preproc_out_handle, self.process_listeners_callback)
        self.preproc_out_offset = preproc_out_handle.tell()

        rc = self.process.poll()
        if rc != None:
            self.log.debug("Preproc RC %s", rc)
            return rc
        else:
            return -1

    def apply_buffer_to_draft(self):
        if self.buffer: # if it is still not empty - force processing
            self.second_data_draft += [self.buffer]
            self.buffer = []

    def end_test(self, rc):
        time.sleep(1)
        if self.process:
            self.log.debug("Reading rests of preproc out")
            self.is_test_finished()
            self.apply_buffer_to_draft()
                
        if self.second_data_draft:
            self.log.debug("Unprocessed second data: %s", self.second_data_draft)
            self.process_listeners_callback(self.second_data_draft)
            self.second_data_draft = []    

        if self.process and self.process.poll() == None:
            self.log.debug("Terminating preproc process with PID %s", self.process.pid)
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.terminate()
            except Exception, ex:
                self.log.warning("Failed to kill preproc process with pid %s: %s", self.process.pid, ex)
        else:
            self.log.warn("Seems the preproc has been finished")

        return rc        
        
        
    def add_result_listener(self, listener):
        self.second_data_listeners += [listener]
    
    def set_source_files(self, phout, stat):
        self.phout_file = phout
        self.core.set_option(self.SECTION, self.OPTION_SOURCE_FILE, self.phout_file)
        self.threads_file = stat
        self.core.set_option(self.SECTION, self.OPTION_STAT_FILE, self.threads_file)

    def get_timeout(self):
        return self.time_periods.split(' ')[-1:][0]

class SecondAggregateData:
    def __init__(self, cases_draft):
        self.cases = {}
        self.time = None
        # @type self.overall: SecondAggregateDataItem
        self.overall = None
        for lines in cases_draft:
            #logging.debug("Draft lines: %s", lines)
            data_item = SecondAggregateDataItem(lines)
            if data_item.overall:
                self.overall = data_item
            else:
                self.cases[data_item.case] = data_item
                
            if not self.time:
                self.time = data_item.time
            elif data_item.time != self.time:
                    raise RuntimeError("Several seconds in preproc records group: %s != %s" % (self.time, data_item.time))
        if not self.overall:
                raise RuntimeError("Cannot go without overall info")                
            

class SecondAggregateDataItem:
    T_OVERALL = "overall="
    T_CASE = "case="
    T_TIMESTAMP = "time="
    T_REQPS = "reqps="
    T_TASKS = "tasks="
    T_SELFLOAD = "selfload="
    T_OUTPUT = "output="
    T_INPUT = "input="
    
    T_CONNECT = "connect_time_expect="
    T_SEND = "send_time_expect="
    T_LATENCY = "latency_expect="
    T_RECEIVE = "receive_time_expect="
    T_AVG_RT = "interval_real_expect="
    
    T_HTTP_CODE = "HTTPcode="
    T_NET_CODE = "netwcode="
    T_TIMES = "answ_time="

    T_DISPERSION = "dispersion="

    def parse_singles(self, line):
        if line.startswith(self.T_OVERALL):
            self.overall = int(line.strip()[len(self.T_OVERALL):])
        if line.startswith(self.T_CASE):
            self.case = line.strip()[len(self.T_CASE):]
        if line.startswith(self.T_TIMESTAMP):
            self.time = datetime.datetime.strptime(line.strip()[len(self.T_TIMESTAMP):], "%Y%m%d%H%M%S")
        if line.startswith(self.T_REQPS):
            self.planned_requests = int(line.strip()[len(self.T_REQPS):])
        if line.startswith(self.T_TASKS):
            self.active_threads = int(line.strip()[len(self.T_TASKS):])
        if line.startswith(self.T_INPUT):
            self.input = int(line.strip()[len(self.T_INPUT):])
        if line.startswith(self.T_OUTPUT):
            self.output = int(line.strip()[len(self.T_OUTPUT):])
        if line.startswith(self.T_SELFLOAD):
            selfload = line.strip()[len(self.T_SELFLOAD):]
            if selfload != "0":
                self.selfload = float(selfload[:-1])
            else: 
                self.selfload = 0


    def parse_avg_times(self, line):
        if line.startswith(self.T_CONNECT):
            self.avg_connect_time = float(line.strip()[len(self.T_CONNECT):]) / 1000
        if line.startswith(self.T_SEND):
            self.avg_send_time = float(line.strip()[len(self.T_SEND):]) / 1000
        if line.startswith(self.T_LATENCY):
            self.avg_latency = float(line.strip()[len(self.T_LATENCY):]) / 1000
        if line.startswith(self.T_RECEIVE):
            self.avg_receive_time = float(line.strip()[len(self.T_RECEIVE):]) / 1000
        if line.startswith(self.T_AVG_RT):
            self.avg_response_time = float(line.strip()[len(self.T_AVG_RT):]) / 1000


    def parse_distributions(self, line):
        if line.startswith(self.T_HTTP_CODE):
            times_line = line.strip()[len(self.T_HTTP_CODE):].strip()
            parts = times_line.split(":")
            self.http_codes[parts[0]] = int(parts[1])

        if line.startswith(self.T_NET_CODE):
            times_line = line.strip()[len(self.T_NET_CODE):].strip()
            parts = times_line.split(":")
            self.net_codes[parts[0]] = int(parts[1])

        if line.startswith(self.T_TIMES):
            times_line = line.strip()[len(self.T_TIMES):].strip()
            parts = times_line.split(":")
            interval = parts[0].split('-')
            self.times_dist += [{"from": int(interval[0]), "to": int(interval[1]), "count": int(parts[1])}]

    
    def parse_quantiles(self, line):
        if self.T_DISPERSION in line:
            line = line.strip()
            dis = line[line.find(self.T_DISPERSION) + len(self.T_DISPERSION):]
            self.dispersion = float(dis)
        
        if "_q" in line:
            parts = line.split("=")
            level_parts = parts[0].split("_q")
            self.quantiles[level_parts[1]] = int(parts[1]) / 1000
        
    
    
    def __init__(self, lines):
        self.log = logging.getLogger(__name__)
        self.overall = None
        self.case = None
        self.time = None
        self.planned_requests = None
        self.active_threads = None
        self.selfload = None
        self.RPS = None

        self.http_codes = {}
        self.net_codes = {}
        self.times_dist = []
        self.quantiles = {}
        for line in lines:
            line = line.strip()
            #self.log.debug("Parsing line: %s", line)
            self.parse_singles(line)
            self.parse_avg_times(line)
            self.parse_distributions(line)
            self.parse_quantiles(line)
        self.RPS = sum(self.net_codes.values())

# TODO: add cumulative values to items
