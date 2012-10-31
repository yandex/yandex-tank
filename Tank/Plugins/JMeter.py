''' jmeter load generator support '''
from Tank.Plugins.Aggregator import AbstractReader, AggregatorPlugin, \
    AggregateResultListener
from Tank.Plugins.ConsoleOnline import ConsoleOnlinePlugin, AbstractInfoWidget
import os
import signal
import subprocess
import tempfile
from tankcore import AbstractPlugin
import tankcore


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


    @staticmethod
    def get_key():
        return __file__

    
    def configure(self):
        self.original_jmx = self.get_option("jmx")
        self.core.add_artifact_file(self.original_jmx, True)
        self.jtl_file = self.core.mkstemp('.jtl', 'jmeter_')
        self.core.add_artifact_file(self.jtl_file)
        self.jmx = self.__add_writing_section(self.original_jmx, self.jtl_file)
        self.core.add_artifact_file(self.jmx)
        self.user_args = self.get_option("args", '')
        self.jmeter_path = self.get_option("jmeter_path", 'jmeter')
        self.jmeter_log = self.core.mkstemp('.log', 'jmeter_')
        self.core.add_artifact_file(self.jmeter_log, True)


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
        self.jmeter_process = subprocess.Popen(self.args, executable=self.jmeter_path, preexec_fn=os.setsid, close_fds=True) # stderr=subprocess.PIPE, stdout=subprocess.PIPE, 
    
    
    def is_test_finished(self):
        retcode = self.jmeter_process.poll()
        if retcode != None:
            self.log.info("JMeter process finished with exit core: %s", retcode)
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
            #Utils.log_stdout_stderr(self.log, self.jmeter_process.stdout, self.jmeter_process.stderr, "jmeter")

        self.core.add_artifact_file(self.jmeter_log)
        return retcode

            
    def __add_writing_section(self, jmx, jtl):
        '''
        Genius idea by Alexey Lavrenyuk
        '''
        self.log.debug("Original JMX: %s", os.path.realpath(jmx))
        source_lines = open(jmx, 'r').readlines()
        try:
            closing = source_lines.pop(-1)
            closing = source_lines.pop(-1) + closing
            closing = source_lines.pop(-1) + closing
        except Exception, exc:
            self.log.error("Failed to find the end of JMX XML: %s", exc)
        self.log.debug("Closing statement: %s", closing)
        
        tpl = open(os.path.dirname(__file__) + '/jmeter_writer.xml', 'r').read()
        
        try:
            file_handle, new_file = tempfile.mkstemp('.jmx', 'modified_', os.path.dirname(os.path.realpath(jmx)))
        except OSError, exc:
            self.log.debug("Can't create new jmx near original: %s", exc)
            file_handle, new_file = tempfile.mkstemp('.jmx', 'modified_', self.core.artifacts_base_dir)
        self.log.debug("Modified JMX: %s", new_file)
        os.write(file_handle, ''.join(source_lines))
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
    
    def check_open_files(self):
        if not self.results and os.path.exists(self.jmeter.jtl_file):
            self.log.debug("Opening jmeter out file: %s", self.jmeter.jtl_file)
            self.results = open(self.jmeter.jtl_file, 'r')
            
    def close_files(self):
        if self.results:
            self.results.close()

    def get_next_sample(self, force):
        if self.results:
            read_lines = self.results.readlines()
            self.log.debug("About to process %s result lines", len(read_lines))
            for line in read_lines:
                line = line.strip()
                if not line:
                    return None 
                #timeStamp,elapsed,label,responseCode,success,bytes,grpThreads,allThreads,Latency
                data = line.split("\t")
                if len(data) != 9:
                    self.log.warning("Wrong jtl line, skipped: %s", line)
                    continue
                cur_time = int(data[0]) / 1000
                netcode = '0' if data[4] == 'true' else self.exc_to_net(data[3]) 
                
                if not cur_time in self.data_buffer.keys():
                    if self.data_queue and self.data_queue[-1] >= cur_time:
                        self.log.warning("Aggregator data dates must be sequential: %s vs %s" % (cur_time, self.data_queue[-1]))
                        cur_time = self.data_queue[-1]
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
                    
        if len(self.data_queue) > 2:
            return self.pop_second()
        
        if force and self.data_queue:
            return self.pop_second()
        else:
            return None 

    def exc_to_net(self, param1):
        ''' translate http code to net code '''
        if len(param1) <= 3:
            return '0'
        
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

class JMeterInfoWidget(AbstractInfoWidget, AggregateResultListener):
    ''' Right panel widget with JMeter test info '''
    def __init__(self, jmeter):
        AbstractInfoWidget.__init__(self)
        self.jmeter = jmeter
        self.active_threads = 0
        self.rps = 0

    def get_index(self):
        return 0

    def aggregate_second(self, second_aggregate_data):
        self.active_threads = second_aggregate_data.overall.active_threads
        self.rps = second_aggregate_data.overall.RPS

    def render(self, screen):        
        jmeter = " JMeter Test "
        space = screen.right_panel_width - len(jmeter) - 1 
        left_spaces = space / 2
        right_spaces = space / 2
        template = screen.markup.BG_MAGENTA + '~' * left_spaces + jmeter + ' ' + '~' * right_spaces + screen.markup.RESET + "\n" 
        template += "     Test Plan: %s\n"
        template += "Active Threads: %s\n"
        template += "   Responses/s: %s"
        data = (os.path.basename(self.jmeter.original_jmx), self.active_threads, self.rps)
        
        return template % data
