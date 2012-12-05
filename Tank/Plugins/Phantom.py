'''
Contains Phantom Plugin, Console widgets, result reader classes
'''
from Tank.Plugins.Aggregator import AggregatorPlugin, AggregateResultListener, \
    AbstractReader
from Tank.Plugins.Autostop import AutostopPlugin, AbstractCriteria
from Tank.Plugins.ConsoleOnline import ConsoleOnlinePlugin, AbstractInfoWidget
from Tank.Plugins.Stepper import Stepper
from ipaddr import AddressValueError
from tankcore import AbstractPlugin
import ConfigParser
import datetime
import hashlib
import ipaddr
import multiprocessing
import os
import socket
import string
import subprocess
import sys
import tankcore
import time
import logging

# TODO: 2 if instances_schedule enabled - pass to phantom the top count as instances limit
# FIXME: 3 there is no graceful way to interrupt the process in phout import mode 
class PhantomPlugin(AbstractPlugin, AggregateResultListener):
    '''
    Plugin for running phantom tool
    '''
    SECTION = 'phantom'
    
    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.process = None
        self.phout_import_mode = 0
        self.did_phout_import_try = False
        self.phantom_path = None
        self.eta_file = None
        self.processed_ammo_count = 0
        self.config = None
        self.stepper = None
        self.phantom = None
        self.phantom_start_time = time.time()
                
    
    @staticmethod
    def get_key():
        return __file__
    
    
    def configure(self):       
        # plugin part
        self.config = self.get_option("config", '')
        self.eta_file = self.get_option("eta_file", '')
        self.phantom_path = self.get_option("phantom_path", 'phantom')
        
        self.core.add_artifact_file(self.eta_file)        
        self.core.add_artifact_file(self.config)

        self.phout_import_mode = self.get_option(PhantomConfig.OPTION_PHOUT, '')

        try:
            autostop = self.core.get_plugin_of_type(AutostopPlugin)
            autostop.add_criteria_class(UsedInstancesCriteria)
        except KeyError:
            self.log.debug("No autostop plugin found, not adding instances criteria")
            
        if not self.config and not self.phout_import_mode:
            self.phantom = PhantomConfig(self)
            self.phantom.read_config()
            self.stepper = StepperWrapper(self)
            self.stepper.read_config()
       

    def prepare_test(self):
        aggregator = None
        try:
            aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        except Exception, ex:
            self.log.warning("No aggregator found: %s", ex)

        if aggregator:
            aggregator.reader = PhantomReader(aggregator, self)
            if self.phantom:
                self.phantom.timeout = aggregator.get_timeout()
            aggregator.add_result_listener(self)

        if not self.phout_import_mode:
            self.stepper.prepare_stepper()     
            self.phantom.stpd = self.stepper.stpd
                
            if not self.config:
                self.config = self.phantom.compose_config()
            args = [self.phantom_path, 'check', self.config]
            
            retcode = tankcore.execute(args, catch_out=True)[0]
            if retcode:
                raise RuntimeError("Subprocess returned %s" % retcode)    

        try:
            console = self.core.get_plugin_of_type(ConsoleOnlinePlugin)
        except Exception, ex:
            self.log.debug("Console not found: %s", ex)
            console = None
            
        if console:
            if not self.phout_import_mode:    
                widget = PhantomProgressBarWidget(self)
                if self.eta_file:
                    widget.eta_file = self.eta_file
                console.add_info_widget(widget)
                aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
                aggregator.add_result_listener(widget)

            widget = PhantomInfoWidget(self)
            console.add_info_widget(widget)
            aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
            aggregator.add_result_listener(widget)

        
    def start_test(self):
        if not self.phout_import_mode:
            args = [self.phantom_path, 'run', self.config]
            self.log.debug("Starting %s with arguments: %s", self.phantom_path, args)
            self.phantom_start_time = time.time()
            self.process = subprocess.Popen(args, stderr=subprocess.PIPE, stdout=subprocess.PIPE, close_fds=True)
        else:
            if not os.path.exists(self.phout_import_mode):
                raise RuntimeError("Phout file not exists for import: %s" % self.phout_import_mode)
            self.log.warn("Will import phout file instead of running phantom: %s", self.phout_import_mode)
    

    def is_test_finished(self):
        if not self.phout_import_mode:
            tankcore.log_stdout_stderr(self.log, self.process.stdout, self.process.stderr, self.SECTION)
    
            retcode = self.process.poll()
            if retcode != None:
                self.log.info("Phantom done its work with exit code: %s", retcode)
                return retcode
            else:
                return -1
        else:
            if not self.processed_ammo_count or self.did_phout_import_try != self.processed_ammo_count:
                self.did_phout_import_try = self.processed_ammo_count
                return -1
            else:
                return 0
    
    
    def end_test(self, retcode):
        if self.process and self.process.poll() == None:
            self.log.warn("Terminating phantom process with PID %s", self.process.pid)
            self.process.terminate()
        else:
            self.log.debug("Seems phantom finished OK")
        return retcode

            
    def post_process(self, retcode):
        if not retcode:
            count = int(self.get_option(StepperWrapper.OPTION_AMMO_COUNT))
            if count != self.processed_ammo_count:
                self.log.warning("Planned ammo count %s differs from processed %s", count, self.processed_ammo_count)
        return retcode


    def aggregate_second(self, second_aggregate_data):
        self.processed_ammo_count += second_aggregate_data.overall.RPS
        self.log.debug("Processed ammo count: %s/", self.processed_ammo_count);

            

class PhantomProgressBarWidget(AbstractInfoWidget, AggregateResultListener):
    '''
    Widget that displays progressbar
    '''
    def get_index(self):
        return 0

    def __init__(self, sender):
        AbstractInfoWidget.__init__(self)
        self.owner = sender 
        self.ammo_progress = 0
        self.ammo_count = int(self.owner.core.get_option(PhantomPlugin.SECTION, StepperWrapper.OPTION_AMMO_COUNT))
        self.test_duration = int(self.owner.core.get_option(PhantomPlugin.SECTION, StepperWrapper.OPTION_TEST_DURATION))
        self.eta_file = None

    def render(self, screen):
        res = ""

        dur_seconds = int(time.time()) - int(self.owner.phantom_start_time)

        eta_time = 'N/A' 
        eta_secs = -1
        progress = 0
        color_bg = screen.markup.BG_CYAN
        color_fg = screen.markup.CYAN
        if self.test_duration and self.test_duration >= dur_seconds:
            color_bg = screen.markup.BG_GREEN
            color_fg = screen.markup.GREEN
            eta_secs = self.test_duration - dur_seconds
            eta_time = datetime.timedelta(seconds=eta_secs)
            progress = float(dur_seconds) / self.test_duration
        elif self.ammo_progress:
            left_part = self.ammo_count - self.ammo_progress
            eta_secs = int(float(dur_seconds) / float(self.ammo_progress) * float(left_part))
            eta_time = datetime.timedelta(seconds=eta_secs)
            progress = float(self.ammo_progress) / float(self.ammo_count)

        if self.eta_file:
            handle = open(self.eta_file, 'w')
            handle.write(str(eta_secs))
            handle.close()

        perc = float(int(1000 * progress)) / 10
        str_perc = str(perc) + "%"
        
        pb_width = screen.right_panel_width - 1 - len(str_perc)
        
        res += color_bg + '=' * int(pb_width * progress) + screen.markup.RESET + color_fg + '~' * (pb_width - int(pb_width * progress)) + screen.markup.RESET + ' '
        res += str_perc + "\n"

        eta = 'ETA: %s' % eta_time
        dur = 'Duration: %s' % str(datetime.timedelta(seconds=dur_seconds))
        spaces = ' ' * (screen.right_panel_width - len(eta) - len(dur) - 1)
        res += dur + ' ' + spaces + eta

        return res

    def aggregate_second(self, second_aggregate_data):
        self.ammo_progress += second_aggregate_data.overall.RPS


class PhantomInfoWidget(AbstractInfoWidget, AggregateResultListener):
    '''
    Widget with information about current run state
    '''
    def get_index(self):
        return 2

    def __init__(self, sender):
        AbstractInfoWidget.__init__(self)
        self.owner = sender 
        self.instances = 0
        self.planned = 0
        self.RPS = 0    
        self.instances_limit = int(self.owner.core.get_option(PhantomPlugin.SECTION, PhantomConfig.OPTION_INSTANCES_LIMIT))
        self.ammo_count = int(self.owner.core.get_option(PhantomPlugin.SECTION, StepperWrapper.OPTION_AMMO_COUNT))
        self.selfload = 0
        self.time_lag = 0
        self.planned_rps_duration = 0

    def render(self, screen):
        if self.owner.phantom and self.owner.stepper:
            template = "Hosts: %s => %s:%s\n Ammo: %s\nCount: %s\n Load: %s"
            data = (socket.gethostname(), self.owner.phantom.address, self.owner.phantom.port, os.path.basename(self.owner.stepper.ammo_file), self.ammo_count, ' '.join(self.owner.stepper.rps_schedule))
            res = template % data
            
            res += "\n\n"
        
        res += "Active instances: "
        if float(self.instances) / self.instances_limit > 0.8:
            res += screen.markup.RED + str(self.instances) + screen.markup.RESET
        elif float(self.instances) / self.instances_limit > 0.5:
            res += screen.markup.YELLOW + str(self.instances) + screen.markup.RESET
        else:
            res += str(self.instances)
            
        res += "\nPlanned requests: %s for %s\nActual responses: " % (self.planned, datetime.timedelta(seconds=self.planned_rps_duration))
        if not self.planned == self.RPS:
            res += screen.markup.YELLOW + str(self.RPS) + screen.markup.RESET
        else:
            res += str(self.RPS)
                
        res += "\n        Accuracy: "
        if self.selfload < 80:
            res += screen.markup.RED + ('%.2f' % self.selfload) + screen.markup.RESET
        elif self.selfload < 95:
            res += screen.markup.YELLOW + ('%.2f' % self.selfload) + screen.markup.RESET
        else:
            res += ('%.2f' % self.selfload)

        res += "%\n        Time lag: "        
        if self.time_lag > 15:
            res += screen.markup.RED + str(datetime.timedelta(seconds=self.time_lag)) + screen.markup.RESET
        elif self.time_lag > 3:
            res += screen.markup.YELLOW + str(datetime.timedelta(seconds=self.time_lag)) + screen.markup.RESET
        else:
            res += str(datetime.timedelta(seconds=self.time_lag))
                
        return res

    def aggregate_second(self, second_aggregate_data):
        self.instances = second_aggregate_data.overall.active_threads
        if self.planned == second_aggregate_data.overall.planned_requests:
            self.planned_rps_duration += 1
        else:
            self.planned = second_aggregate_data.overall.planned_requests
            self.planned_rps_duration = 1
        
        self.RPS = second_aggregate_data.overall.RPS
        self.selfload = second_aggregate_data.overall.selfload
        self.time_lag = int(time.time() - time.mktime(second_aggregate_data.time.timetuple()))
    
    
class PhantomReader(AbstractReader):
    '''
    Adapter to read phout files
    '''

    def __init__(self, owner, phantom):
        AbstractReader.__init__(self, owner)
        self.phantom = phantom
        self.phout = None
        self.stat = None
        self.stat_data = {}
        self.pending_datetime = None
        self.steps = []
        self.first_request_time = sys.maxint
        self.partial_buffer = ''
        self.pending_second_data_queue = []
        self.last_sample_time = 0
        self.read_lines_count = 0
  
    def check_open_files(self):
        if not self.phout and self.phantom.phantom and os.path.exists(self.phantom.phantom.phout_file):
            self.log.debug("Opening phout file: %s", self.phantom.phantom.phout_file)
            self.phout = open(self.phantom.phantom.phout_file, 'r')
            # strange decision to place it here, but no better idea yet
            if self.phantom.stepper:
                for item in tankcore.pairs(self.phantom.stepper.steps):
                    self.steps.append([item[0], item[1]])  
    
        if not self.stat and self.phantom.phantom and self.phantom.phantom.stat_log and os.path.exists(self.phantom.phantom.stat_log):
            self.log.debug("Opening stat file: %s", self.phantom.phantom.stat_log)
            self.stat = open(self.phantom.phantom.stat_log, 'r')

    def close_files(self):
        if self.stat:
            self.stat.close()
            
        if self.phout:
            self.phout.close()

    def get_next_sample(self, force):
        if self.stat: 
            self.__read_stat_data()
        return self.__read_phout_data(force)

    def __read_stat_data(self):
        '''
        Read active instances info
        '''
        stat = self.stat.readlines()
        for line in stat:
            if line.startswith('time\t'):
                date_str = line[len('time:\t') - 1:].strip()[:-5].strip()
                date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                self.pending_datetime = int(time.mktime(date_obj.timetuple()))
                self.stat_data[self.pending_datetime] = 0
            if line.startswith('tasks\t'):
                if not self.pending_datetime:
                    raise RuntimeError("Can't have tasks info without timestamp")
                
                self.stat_data[self.pending_datetime] = max(int(line[len('tasks\t'):]), self.stat_data[self.pending_datetime])
                self.log.debug("Active instances: %s=>%s", self.pending_datetime, self.stat_data[self.pending_datetime])


    def __read_phout_data(self, force):
        '''
        Read phantom results
        '''
        if self.phout:
            phout = self.phout.readlines(5 * 1024 * 1024)
        else:
            phout = []
    
        self.log.debug("About to process %s phout lines", len(phout))
        for line in phout:
            line = self.partial_buffer + line
            self.partial_buffer = ''
            if line[-1] != "\n":
                self.log.debug("Not complete line, buffering it: %s", line)
                self.partial_buffer = line
                continue
            line = line.strip()
            if not line:
                self.log.warning("Empty phout line")
                continue
            #1346949510.514        74420    66    78    65409    8867    74201    18    15662    0    200
            #self.log.debug("Phout line: %s", line)
            self.read_lines_count += 1
            data = line.split("\t")
            if len(data) != 12:
                self.log.warning("Wrong phout line, skipped: %s", line)
                continue
            cur_time = int(float(data[0]) + float(data[2]) / 1000000)
            #self.log.info("%s => %s", data[0], cur_time)
            try:
                active = self.stat_data[cur_time]
            except KeyError:
                #self.log.debug("No tasks info for second yet: %s", cur_time)
                active = 0

            if not cur_time in self.data_buffer.keys():
                self.first_request_time = min(self.first_request_time, int(float(data[0])))
                if self.data_queue and self.data_queue[-1] >= cur_time:
                    self.log.warning("Aggregator data dates must be sequential: %s vs %s" % (cur_time, self.data_queue[-1]))
                    cur_time = self.data_queue[-1]
                else:
                    self.data_queue.append(cur_time)
                    self.data_buffer[cur_time] = []
            #        marker, threads, overallRT, httpCode, netCode
            data_item = [data[1], active, int(data[2]) / 1000, data[11], data[10]]
            # bytes:     sent    received
            data_item += [int(data[8]), int(data[9])]
            #        connect    send    latency    receive
            data_item += [int(data[3]) / 1000, int(data[4]) / 1000, int(data[5]) / 1000, int(data[6]) / 1000]
            #        accuracy
            data_item += [(float(data[7]) + 1) / (int(data[2]) + 1)]
            self.data_buffer[cur_time].append(data_item)

        self.log.debug("Read lines: %s", self.read_lines_count)                    
        self.log.debug("Seconds queue: %s", self.data_queue)
        self.log.debug("Seconds buffer: %s", self.data_buffer.keys())
        if len(self.data_queue) > 3:
            return self.pop_second()
        
        if force and self.data_queue:
            return self.pop_second()
        else:
            self.log.debug("No queue data!")
            return None 


    def pop_second(self):
        parsed_sec = AbstractReader.pop_second(self)
        if parsed_sec:
            self.pending_second_data_queue.append(parsed_sec)
        else:
            self.log.debug("No new seconds present")   
            
        if not self.pending_second_data_queue:
            self.log.debug("pending_second_data_queue empty")
            return None
        else:
            self.log.debug("pending_second_data_queue: %s", self.pending_second_data_queue)


        next_time = int(time.mktime(self.pending_second_data_queue[0].time.timetuple()))
            
        if self.last_sample_time and (next_time - self.last_sample_time) > 1:
            self.last_sample_time += 1
            self.log.warning("Adding phantom zero sample: %s", self.last_sample_time)
            res = self.get_zero_sample(datetime.datetime.fromtimestamp(self.last_sample_time))
        else:
            res = self.pending_second_data_queue.pop(0)
        
        self.last_sample_time = int(time.mktime(res.time.timetuple()))
        res.overall.planned_requests = self.__get_expected_rps()
        self.log.debug("Pop result: %s", res)
        return res
    

    def __get_expected_rps(self):
        '''
        Mark second with expected rps from stepper info
        '''
        while self.steps and self.steps[0][1] < 1:
            self.steps.pop(0)
        
        if not self.steps:
            return 0
        else:
            self.steps[0][1] -= 1
            return self.steps[0][0]
            
     
class UsedInstancesCriteria(AbstractCriteria):
    '''
    Autostop criteria, based on active instances count
    '''
    RC_INST = 24
    
    @staticmethod
    def get_type_string():
        return 'instances'

    def __init__(self, autostop, param_str):
        AbstractCriteria.__init__(self)
        self.seconds_count = 0
        self.autostop = autostop

        level_str = param_str.split(',')[0].strip()
        if level_str[-1:] == '%':
            self.level = float(level_str[:-1]) / 100
            self.is_relative = True
        else:
            self.level = int(level_str)
            self.is_relative = False
        self.seconds_limit = tankcore.expand_to_seconds(param_str.split(',')[1])
        
        try:
            phantom = autostop.core.get_plugin_of_type(PhantomPlugin)
            self.threads_limit = phantom.phantom.instances
            if not self.threads_limit:
                raise ValueError("Cannot create 'instances' criteria with zero instances limit")
        except KeyError:
            self.log.warning("No phantom module, 'instances' autostop disabled")


    def notify(self, aggregate_second):
        threads = aggregate_second.overall.active_threads
        if self.is_relative:
            threads = float(threads) / self.threads_limit
        if threads > self.level:
            if not self.seconds_count:
                self.cause_second = aggregate_second
            
            self.log.debug(self.explain())
            
            self.seconds_count += 1
            self.autostop.add_counting(self)
            if self.seconds_count >= self.seconds_limit:
                return True
        else:
            self.seconds_count = 0
            
        return False

    def get_rc(self):
        return self.RC_INST

    def get_level_str(self):
        '''
        String value for instances level
        '''
        if self.is_relative:
            level_str = str(100 * self.level) + "%"
        else:
            level_str = self.level
        return level_str

    def explain(self):
        items = (self.get_level_str(), self.seconds_count, self.cause_second.time)
        return "Testing threads (instances) utilization higher than %s for %ss, since %s" % items                 

    def widget_explain(self):
        items = (self.get_level_str(), self.seconds_count, self.seconds_limit)
        return ("Instances >%s for %s/%ss" % items, float(self.seconds_count) / self.seconds_limit)

class PhantomConfig:
    ''' config file generator '''
    OPTION_INSTANCES_LIMIT = 'instances'
    OPTION_PHOUT = "phout_file"
    OPTION_STPD = 'stpd_file'
    
    def __init__(self, owner):
        self.owner = owner
        self.log = logging.getLogger(__name__)
        # phant
        self.timeout = -1
        self.answ_log = None
        self.phout_file = None
        self.stat_log = None
        self.phantom_log = None
        self.instances = None
        self.phantom_start_time = None
        self.ipv6 = None
        self.phantom_modules_path = None
        self.ssl = None
        self.address = None
        self.port = None
        self.tank_type = None
        self.answ_log_level = None
        self.stpd = None
        self.threads = None
        self.gatling = None
        self.phantom_http_line = None
        self.phantom_http_field_num = None
        self.phantom_http_field = None
        self.phantom_http_entity = None
        self.resolved_ip = None


    def get_option(self, option_ammofile, param2=None):
        ''' get option wrapper '''
        return self.owner.get_option(option_ammofile, param2)
    
    
    def __resolve_address(self):
        '''        Analyse target address setting, resolve it to IP        '''
        if not self.address:
            raise RuntimeError("Target address not specified")
        try:
            ipaddr.IPv6Address(self.address)
            self.ipv6 = True
            self.resolved_ip = self.address
        except AddressValueError:
            self.log.debug("Not ipv6 address: %s", self.address)
            self.ipv6 = False
            address_port = self.address.split(":")
            self.address = address_port[0]
            if len(address_port) > 1:
                self.port = address_port[1]
            try:
                ipaddr.IPv4Address(self.address)
                self.resolved_ip = self.address
            except AddressValueError:
                self.log.debug("Not ipv4 address: %s", self.address)
                ip_addr = socket.gethostbyname(self.address)
                reverse_name = socket.gethostbyaddr(ip_addr)[0]
                self.log.debug("Address %s ip_addr: %s, reverse-resolve: %s", self.address, ip_addr, reverse_name)
                if reverse_name.startswith(self.address):
                    self.resolved_ip = ip_addr
                else:
                    raise ValueError("Address %s reverse-resolved to %s, but must match" % (self.address, reverse_name))


    def read_config(self):
        '''        Read phantom tool specific options        '''
        self.phantom_modules_path = self.get_option("phantom_modules_path", "/usr/lib/phantom")
        self.ssl = int(self.get_option("ssl", '0'))
        self.tank_type = self.get_option("tank_type", 'http')
        self.answ_log_level = self.get_option("writelog", "none")
        if self.answ_log_level == '0':
            self.answ_log_level = 'none'
        elif self.answ_log_level == '1':
            self.answ_log_level = 'all'
            
        self.answ_log = self.owner.core.mkstemp(".log", "answ_")            
        self.phout_file = self.owner.core.mkstemp(".log", "phout_")
        self.owner.core.add_artifact_file(self.phout_file)

        self.stat_log = self.owner.core.mkstemp(".log", "phantom_stat_")
        self.phantom_log = self.owner.core.mkstemp(".log", "phantom_")
        self.stpd = self.get_option(self.OPTION_STPD, '')
        self.threads = self.get_option("threads", int(multiprocessing.cpu_count() / 2) + 1)
        self.instances = int(self.get_option(self.OPTION_INSTANCES_LIMIT, '1000'))
        self.gatling = ' '.join(self.get_option('gatling_ip', '').split("\n"))
        self.phantom_http_line = self.get_option("phantom_http_line", "")
        self.phantom_http_field_num = self.get_option("phantom_http_field_num", "")
        self.phantom_http_field = self.get_option("phantom_http_field", "")
        self.phantom_http_entity = self.get_option("phantom_http_entity", "")

        self.address = self.get_option('address', 'localhost')
        self.port = self.get_option('port', '80')
        self.__resolve_address()            

        self.owner.core.add_artifact_file(self.answ_log)        
        self.owner.core.add_artifact_file(self.stat_log)
        self.owner.core.add_artifact_file(self.phantom_log)

    def compose_config(self):
        '''        Generate phantom tool run config        '''
        if not self.stpd:
            raise RuntimeError("Cannot proceed with no source file")
        
        kwargs = {}
        kwargs['ssl_transport'] = "transport_t ssl_transport = transport_ssl_t { timeout = 1s } transport = ssl_transport" if self.ssl else ""
        kwargs['method_stream'] = "method_stream_ipv6_t" if self.ipv6 else "method_stream_ipv4_t"            
        kwargs['proto'] = "http_proto" if self.tank_type == 'http' else "none_proto"
        kwargs['threads'] = self.threads
        kwargs['answ_log'] = self.answ_log
        kwargs['answ_log_level'] = self.answ_log_level
        kwargs['comment_answ'] = "# " if self.answ_log_level == 'none' else ''
        kwargs['phout'] = self.phout_file
        kwargs['stpd'] = self.stpd
        if self.gatling:
            kwargs['bind'] = 'bind={ ' + self.gatling + ' }'
        else: 
            kwargs['bind'] = '' 
        kwargs['ip'] = self.resolved_ip
        kwargs['port'] = self.port
        kwargs['timeout'] = self.timeout
        kwargs['instances'] = self.instances
        kwargs['stat_log'] = self.stat_log
        kwargs['phantom_log'] = self.phantom_log
        tune = ''
        if self.phantom_http_entity:
            tune += "entity = " + self.phantom_http_entity + "\n"
        if self.phantom_http_field:
            tune += "field = " + self.phantom_http_field + "\n"
        if self.phantom_http_field_num:
            tune += "field_num = " + self.phantom_http_field_num + "\n"
        if self.phantom_http_line:
            tune += "line = " + self.phantom_http_line + "\n"
        if tune:
            kwargs['reply_limits'] = 'reply_limits = {\n' + tune + "}"
        else:
            kwargs['reply_limits'] = ''

        
        filename = self.owner.core.mkstemp(".conf", "phantom_")
        self.owner.core.add_artifact_file(filename)
        self.log.debug("Generating phantom config: %s", filename)
        template_str = open(os.path.dirname(__file__) + "/phantom.conf.tpl", 'r').read()
        tpl = string.Template(template_str)
        config = tpl.substitute(kwargs)

        handle = open(filename, 'w')
        handle.write(config)
        handle.close()
        return filename
        

    
class StepperWrapper:
    '''
    Wrapper for cached stepper functionality
    '''
    OPTION_STPD = 'stpd_file'
    OPTION_STEPS = 'steps'
    OPTION_TEST_DURATION = 'test_duration'
    OPTION_AMMO_COUNT = 'ammo_count'
    OPTION_LOOP = 'loop'
    OPTION_LOOP_COUNT = 'loop_count'
    OPTION_AMMOFILE = "ammofile"
    OPTION_SCHEDULE = 'rps_schedule'
    OPTION_LOADSCHEME = 'loadscheme'


    def __init__(self, owner):
        self.owner = owner
        self.log = logging.getLogger(__name__)
        # stepper
        self.rps_schedule = []
        self.use_caching = True
        self.http_ver = '1.0'
        self.steps = []
        self.ammo_file = None
        self.instances_schedule = ''
        self.loop_limit = None
        self.ammo_limit = None
        self.uris = []
        self.headers = []
        self.autocases = 0
        self.cache_dir = '.'
        self.force_stepping = None
        self.stpd = None
        

    def get_option(self, option_ammofile, param2=None):
        ''' get_option wrapper'''
        return self.owner.get_option(option_ammofile, param2)
    
    
    def read_config(self):
        ''' stepper part of reading options '''
        self.ammo_file = self.get_option(self.OPTION_AMMOFILE, '')
        if self.ammo_file:
            self.ammo_file = os.path.expanduser(self.ammo_file)
        self.instances_schedule = self.get_option("instances_schedule", '')
        self.loop_limit = int(self.get_option(self.OPTION_LOOP, "-1"))
        self.ammo_limit = int(self.get_option("ammo_limit", "-1")) # TODO: 3 stepper should implement ammo_limit
        sched = self.get_option(self.OPTION_SCHEDULE, '')
        sched = " ".join(sched.split("\n"))
        sched = sched.split(')')
        self.rps_schedule = [] 
        for step in sched:
            if step.strip():
                self.rps_schedule.append(step.strip() + ')')
        self.uris = self.get_option("uris", '').strip().split("\n")
        while '' in self.uris: 
            self.uris.remove('')
        self.headers = self.get_option("headers", '').strip().split("\n")
        while '' in self.headers: 
            self.headers.remove('')
        self.http_ver = self.get_option("header_http", self.http_ver)
        self.autocases = self.get_option("autocases", '0')
        self.use_caching = int(self.get_option("use_caching", '1'))
        self.cache_dir = os.path.expanduser(self.get_option("cache_dir", self.owner.core.artifacts_base_dir))
        self.force_stepping = int(self.get_option("force_stepping", '0'))
                
    def prepare_stepper(self):
        '''
        Generate test data if necessary
        '''
        self.stpd = self.__get_stpd_filename()
        self.owner.core.set_option(self.owner.SECTION, self.OPTION_STPD, self.stpd)
        if self.use_caching and not self.force_stepping and os.path.exists(self.stpd) and os.path.exists(self.stpd + ".conf"):
            self.log.info("Using cached stpd-file: %s", self.stpd)
            stepper = Stepper(self.stpd) # just to store cached data
            self.__read_cached_options(self.stpd + ".conf", stepper)
        else:
            stepper = self.__make_stpd_file(self.stpd)
        
        self.steps = stepper.steps
        
        #self.core.set_option(AggregatorPlugin.SECTION, AggregatorPlugin.OPTION_CASES, stepper.cases)
        self.owner.core.set_option(self.owner.SECTION, self.OPTION_STEPS, ' '.join([str(x) for x in stepper.steps]))
        self.owner.core.set_option(self.owner.SECTION, self.OPTION_LOADSCHEME, stepper.loadscheme)
        self.owner.core.set_option(self.owner.SECTION, self.OPTION_LOOP_COUNT, str(stepper.loop_count))
        self.owner.core.set_option(self.owner.SECTION, self.OPTION_AMMO_COUNT, str(stepper.ammo_count))
        self.__calculate_test_duration(stepper.steps)
                
        self.owner.core.config.flush(self.stpd + ".conf")

    def __get_stpd_filename(self):
        '''
        Choose the name for stepped data file
        '''
        if self.use_caching:
            sep = "|"
            hasher = hashlib.md5()
            hashed_str = self.instances_schedule + sep + str(self.loop_limit)
            hashed_str += sep + str(self.ammo_limit) + sep + ';'.join(self.rps_schedule) + sep + str(self.autocases)
            hashed_str += sep + ";".join(self.uris) + sep + ";".join(self.headers) + sep + self.http_ver
            
            if self.ammo_file:
                if not os.path.exists(self.ammo_file):
                    raise RuntimeError("Ammo file not found: %s" % self.ammo_file)
            
                hashed_str += sep + os.path.realpath(self.ammo_file)
                stat = os.stat(self.ammo_file)
                cnt = 0
                for stat_option in stat:
                    if cnt == 7: # skip access time
                        continue
                    cnt += 1
                    hashed_str += ";" + str(stat_option)
            else:
                if not self.uris:
                    raise RuntimeError("Neither phantom.ammofile nor phantom.uris specified")
                hashed_str += sep + ';'.join(self.uris) + sep + ';'.join(self.headers)

            self.log.debug("stpd-hash source: %s", hashed_str)
            hasher.update(hashed_str)
            
            if not os.path.exists(self.cache_dir):
                os.makedirs(self.cache_dir)
            stpd = self.cache_dir + '/' + os.path.basename(self.ammo_file) + "_" + hasher.hexdigest() + ".stpd"
            self.log.debug("Generated cache file name: %s", stpd)
        else:
            stpd = os.path.realpath("ammo.stpd")
    
        return stpd

    
    def __calculate_test_duration(self, steps):
        '''
        Get total test duration
        '''        
        duration = 0
        for rps, dur in tankcore.pairs(steps):
            duration += dur
        
        self.owner.core.set_option(self.owner.SECTION, self.OPTION_TEST_DURATION, str(duration))


    def __read_cached_options(self, cached_config, stepper):
        '''
        Merge stpd cached options to current config
        '''
        self.log.debug("Reading cached stepper options: %s", cached_config)
        external_stepper_conf = ConfigParser.ConfigParser()
        external_stepper_conf.read(cached_config)
        #stepper.cases = external_stepper_conf.get(AggregatorPlugin.SECTION, AggregatorPlugin.OPTION_CASES)
        steps = external_stepper_conf.get(PhantomPlugin.SECTION, self.OPTION_STEPS).strip().split(' ')

        if len(steps) % 2 == 0:
            stepper.steps = [int(x) for x in steps]
        else:
            self.log.warning("Steps list must be even: %s", steps)
            stepper.steps = []
        stepper.loadscheme = external_stepper_conf.get(PhantomPlugin.SECTION, self.OPTION_LOADSCHEME)
        stepper.loop_count = external_stepper_conf.get(PhantomPlugin.SECTION, self.OPTION_LOOP_COUNT)
        stepper.ammo_count = external_stepper_conf.get(PhantomPlugin.SECTION, self.OPTION_AMMO_COUNT)


    def __make_stpd_file(self, stpd):
        '''
        stpd generation using Stepper class
        '''
        self.log.info("Making stpd-file: %s", self.stpd)
        stepper = Stepper(stpd)
        stepper.autocases = int(self.autocases)
        stepper.rps_schedule = self.rps_schedule
        stepper.instances_schedule = self.instances_schedule
        stepper.loop_limit = self.loop_limit
        stepper.uris = self.uris
        stepper.headers = self.headers
        stepper.header_http = self.http_ver
        stepper.ammofile = self.ammo_file

        stepper.generate_stpd()
        return stepper
        
