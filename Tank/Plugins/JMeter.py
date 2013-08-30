''' jmeter load generator support '''
from Tank.Plugins.Aggregator import AbstractReader, AggregatorPlugin, \
    AggregateResultListener, SecondAggregateDataItem, SecondAggregateData
from Tank.Plugins.ConsoleOnline import ConsoleOnlinePlugin, AbstractInfoWidget
import os
import signal
import subprocess
import tempfile
from tankcore import AbstractPlugin
import tankcore
from Tank.Plugins import ConsoleScreen
import time
import datetime
import json

class JMeterPlugin(AbstractPlugin):
    ''' JMeter tank plugin '''
    SECTION = 'jmeter'    
    
    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.jmeter_process = None
        self.args = None
        self.original_jmx = None
        self.jtl_file = None
        self.jmx = None
        self.user_args = None
        self.jmeter_path = None
        self.jmeter_log = None
        self.start_time = time.time()
        self.jmeter_buffer_size = None
        self.use_argentum = None

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        return ["jmx", "args", "jmeter_path", "buffer_size", "use_argentum"]
    
    def configure(self):
        self.original_jmx = self.get_option("jmx")
        self.core.add_artifact_file(self.original_jmx, True)
        self.jtl_file = self.core.mkstemp('.jtl', 'jmeter_')
        self.core.add_artifact_file(self.jtl_file)
        self.core.add_artifact_file(self.jmx)
        self.user_args = self.get_option("args", '')
        self.jmeter_path = self.get_option("jmeter_path", 'jmeter')
        self.jmeter_log = self.core.mkstemp('.log', 'jmeter_')
        self.jmeter_buffer_size = int(self.get_option('buffer_size', '3'))
        self.core.add_artifact_file(self.jmeter_log, True)
        self.use_argentum = eval(self.get_option('use_argentum', 'False'))
        self.jmx = self.__add_writing_section(self.original_jmx, self.jtl_file)

    def prepare_test(self):
        self.args = [self.jmeter_path, "-n", "-t", self.jmx, '-j', self.jmeter_log, '-Jjmeter.save.saveservice.default_delimiter=\\t']
        self.args += tankcore.splitstring(self.user_args)
        
        aggregator = None
        try:
            aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        except Exception, ex:
            self.log.warning("No aggregator found: %s", ex)

        if aggregator:
            aggregator.reader = JMeterReader(aggregator, self)
            aggregator.reader.buffer_size = self.jmeter_buffer_size
            aggregator.reader.use_argentum = self.use_argentum

        try:
            console = self.core.get_plugin_of_type(ConsoleOnlinePlugin)
        except Exception, ex:
            self.log.debug("Console not found: %s", ex)
            console = None
            
        if console:    
            widget = JMeterInfoWidget(self)
            console.add_info_widget(widget)
            if aggregator:
                aggregator.add_result_listener(widget)
            
            
    def start_test(self):
        self.log.info("Starting %s with arguments: %s", self.jmeter_path, self.args)
        self.jmeter_process = subprocess.Popen(self.args, executable=self.jmeter_path, preexec_fn=os.setsid, close_fds=True)  # stderr=subprocess.PIPE, stdout=subprocess.PIPE, 
        self.start_time = time.time()
            
    
    def is_test_finished(self):
        retcode = self.jmeter_process.poll()
        if retcode != None:
            self.log.info("JMeter process finished with exit code: %s", retcode)
            return retcode
        else:
            return -1
    
        
    def end_test(self, retcode):
        if self.jmeter_process:
            self.log.info("Terminating jmeter process group with PID %s", self.jmeter_process.pid)
            try:
                os.killpg(self.jmeter_process.pid, signal.SIGTERM)
            except OSError, exc:
                self.log.debug("Seems JMeter exited itself: %s", exc)
            # Utils.log_stdout_stderr(self.log, self.jmeter_process.stdout, self.jmeter_process.stderr, "jmeter")

        self.core.add_artifact_file(self.jmeter_log)
        return retcode

            
    def __add_writing_section(self, jmx, jtl):
        ''' Genius idea by Alexey Lavrenyuk '''
        self.log.debug("Original JMX: %s", os.path.realpath(jmx))
        src_jmx = open(jmx, 'r')
        source_lines = src_jmx.readlines()
        src_jmx.close()
        try:
            closing = source_lines.pop(-1)
            closing = source_lines.pop(-1) + closing
            closing = source_lines.pop(-1) + closing
            self.log.debug("Closing statement: %s", closing)
        except Exception, exc:
            raise RuntimeError("Failed to find the end of JMX XML: %s" % exc)

        tpl_filepath = '/jmeter_writer.xml'

        if self.use_argentum :
            self.log.warn("You are using argentum. Be careful.")
            tpl_filepath = '/jmeter_argentum.xml'
        
        tpl_file = open(os.path.dirname(__file__) + tpl_filepath, 'r')
        tpl = tpl_file.read()
        tpl_file.close()
        
        try:
            file_handle, new_file = tempfile.mkstemp('.jmx', 'modified_', os.path.dirname(os.path.realpath(jmx)))
        except OSError, exc:
            self.log.debug("Can't create new jmx near original: %s", exc)
            file_handle, new_file = tempfile.mkstemp('.jmx', 'modified_', self.core.artifacts_base_dir)
        self.log.debug("Modified JMX: %s", new_file)
        os.write(file_handle, ''.join(source_lines))
        
        if self.use_argentum :
            os.write(file_handle, tpl % (self.jmeter_buffer_size, jtl, "", ""))
        else:
            os.write(file_handle, tpl % jtl)
        os.write(file_handle, closing)
        os.close(file_handle)
        return new_file
    
    
    
class JMeterReader(AbstractReader):
    ''' JTL files reader '''
    KNOWN_EXC = {
        "java.net.NoRouteToHostException": 113,
        "java.net.ConnectException": 110,
        "java.net.BindException":99,
        "java.net.PortUnreachableException":101,
        "java.net.ProtocolException":71,
        "java.net.SocketException":32,
        "java.net.SocketTimeoutException":110,
        "java.net.UnknownHostException":14,
        "java.io.IOException": 5,
        "org.apache.http.conn.ConnectTimeoutException":110,
    }

    def __init__(self, owner, jmeter):
        AbstractReader.__init__(self, owner)
        self.jmeter = jmeter
        self.results = None
        self.partial_buffer = ''
        self.buffer_size = 3
        self.use_argentum = False
    
    def check_open_files(self):
        if not self.results and os.path.exists(self.jmeter.jtl_file):
            self.log.debug("Opening jmeter out file: %s", self.jmeter.jtl_file)
            self.results = open(self.jmeter.jtl_file, 'r')
            
    def close_files(self):
        if self.results:
            self.results.close()

    def get_next_sample(self, force):
        if self.use_argentum :
            return self.get_next_sample_from_ag(force)
        else :
            return self.get_next_sample_from_sdw(force)

    def get_next_sample_from_ag(self, force):
        if self.results:
            read_line = self.results.readline()
            second = None
            if len(read_line) == 0:
                return None
            else :
                try:
                    if self.partial_buffer != '' : 
                        read_line = str(self.partial_buffer + read_line)
                        self.partial_buffer = ''

                    second = json.loads(read_line, 'ascii')
                except ValueError, e:
                    # not-ended second json-object
                    self.partial_buffer = read_line
                    self.log.warn('bad json-object', e)
                    return None
                else:
                    # good json-object. parse it!
                    second_ag = self.get_zero_sample(datetime.datetime.fromtimestamp(second['second']))
                    second_ag.overall.avg_connect_time = 0
                    second_ag.overall.avg_send_time = 0
                    second_ag.overall.avg_receive_time = second['avg_rt'] - second['avg_lt']
                    second_ag.overall.avg_response_time = second['avg_rt']
                    second_ag.overall.avg_latency = second['avg_lt']
                    second_ag.overall.RPS = second['th']
                    second_ag.overall.active_threads = second['active_threads']
                    second_ag.overall.times_dist = second['interval_dist']
                    second_ag.overall.input = second['traffic']['inbound']
                    second_ag.overall.output = second['traffic']['outbound']

                    rc_map = dict()
                    for item in second['rc'].items():
                        rc_map[self.exc_to_http(item[0])] = item[1]
                    second_ag.overall.http_codes = rc_map
                    
                    for percentile in second['percentile'].keys() :
                        second_ag.overall.quantiles[int(float(percentile))] = second['percentile'][percentile]
                        second_ag.cumulative.quantiles[int(float(percentile))] = second['cumulative_percentile'][percentile]

                    self.cumulative.add_data(second_ag.overall)
        
                    for sampler in second['samplers'].keys():
                        sampler_ag_data_item = SecondAggregateDataItem()
                        sampler_ag_data_item.case = sampler
                        sampler_ag_data_item.active_threads = second['active_threads']
                        sampler_ag_data_item.RPS = int(second['samplers'][sampler])
                        sampler_ag_data_item.times_dist =  second['sampler_interval_dist'][sampler]
                        
                        sampler_ag_data_item.quantiles = second['sampler_percentile'][sampler]

                        sampler_ag_data_item.avg_response_time = second['sampler_avg_rt'][sampler]
                        second_ag.cases[sampler] = sampler_ag_data_item
                return second_ag
        return None

    def get_next_sample_from_sdw(self, force):
        if self.results:
            read_lines = self.results.readlines(2*1024*1024)
            self.log.debug("About to process %s result lines", len(read_lines))
            for line in read_lines:
                if not line:
                    return None 
                # timeStamp,elapsed,label,responseCode,success,bytes,grpThreads,allThreads,Latency
                if self.partial_buffer != '':
                    line = self.partial_buffer + line
                    self.partial_buffer = ''
                data = line.rstrip().split("\t")
                if len(data) != 9:
                    self.partial_buffer = line
                    #self.log.warning("Wrong jtl line, skipped: %s", line)
                    continue
                cur_time = int(data[0]) / 1000
                netcode = '0' if data[4] == 'true' else self.exc_to_net(data[3])

                if not cur_time in self.data_buffer.keys():
                    if self.data_queue and self.data_queue[0] >= cur_time:
                        self.log.warning("Aggregator data dates must be sequential: %s vs %s" % (cur_time, self.data_queue[0]))
                        cur_time = self.data_queue[0] # 0 or -1?
                    else:
                        self.data_queue.append(cur_time)
                        self.data_buffer[cur_time] = []
                #        marker, threads, overallRT, httpCode, netCode
                data_item = [data[2], int(data[7]), int(data[1]), self.exc_to_http(data[3]), netcode]
                # bytes:     sent    received
                data_item += [0, int(data[5])]
                #        connect    send    latency    receive
                data_item += [0, 0, int(data[8]), int(data[1]) - int(data[8])]
                #        accuracy
                data_item += [0]
                self.data_buffer[cur_time].append(data_item)
        
        if not force and self.data_queue and (self.data_queue[-1] - self.data_queue[0]) > self.buffer_size:
            return self.pop_second()
        elif force and self.data_queue:
            return self.pop_second()
        else:
            return None

    def exc_to_net(self, param1):
        ''' translate http code to net code '''
        if len(param1) <= 3:
            return '1'
        
        exc = param1.split(' ')[-1] 
        if exc in self.KNOWN_EXC.keys():
            return self.KNOWN_EXC[exc]
        else:
            self.log.warning("Not known Java exception, consider adding it to dictionary: %s", param1)
            return '1'
    
    def exc_to_http(self, param1):
        ''' translate exception str to http code'''
        if len(param1) <= 3:
            return param1
        
        exc = param1.split(' ')[-1] 
        if exc in self.KNOWN_EXC.keys():
            return '0'
        else:
            return '500'

# ===============================================================================

class JMeterInfoWidget(AbstractInfoWidget, AggregateResultListener):
    ''' Right panel widget with JMeter test info '''
    def __init__(self, jmeter):
        AbstractInfoWidget.__init__(self)
        self.krutilka = ConsoleScreen.krutilka()
        self.jmeter = jmeter
        self.active_threads = 0
        self.rps = 0

    def get_index(self):
        return 0

    def aggregate_second(self, second_aggregate_data):
        self.active_threads = second_aggregate_data.overall.active_threads
        self.rps = second_aggregate_data.overall.RPS

    def render(self, screen):        
        jmeter = " JMeter Test %s" % self.krutilka.next()
        space = screen.right_panel_width - len(jmeter) - 1 
        left_spaces = space / 2
        right_spaces = space / 2
        
        dur_seconds = int(time.time()) - int(self.jmeter.start_time)
        duration = str(datetime.timedelta(seconds=dur_seconds))        
        
        template = screen.markup.BG_MAGENTA + '~' * left_spaces + jmeter + ' ' + '~' * right_spaces + screen.markup.RESET + "\n" 
        template += "     Test Plan: %s\n"
        template += "      Duration: %s\n"
        template += "Active Threads: %s\n"
        template += "   Responses/s: %s"
        data = (os.path.basename(self.jmeter.original_jmx), duration, self.active_threads, self.rps)
        
        return template % data
