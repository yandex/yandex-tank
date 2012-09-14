from Tank.Core import AbstractPlugin
from Tank.Plugins.Aggregator import AggregateResultListener, AggregatorPlugin
from Tank.Plugins.Phantom import PhantomPlugin
import json
import logging
import os
import pwd
import socket
import sys
import urllib2
from Tank.Plugins.ConsoleOnline import ConsoleOnlinePlugin, AbstractInfoWidget
from Tank.Plugins.Autostop import AutostopPlugin
import time
from urllib2 import HTTPError
from MonCollector.collector import MonitoringDataListener
from Tank.Plugins.Monitoring import MonitoringPlugin

# TODO: implement interactive metainfo querying
# TODO: implement task=dir
class DataUploaderPlugin(AbstractPlugin, AggregateResultListener, MonitoringDataListener):
    '''
    API Client class for Yandex KSHM web service
    '''
    SECTION = 'meta'
    
    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.api_client = KSHMAPIClient()
        self.jobno = None
        self.logs_basedir = None
        self.operator = pwd.getpwuid(os.geteuid())[0]
        self.task_name = ''
    
    @staticmethod
    def get_key():
        return __file__
    
    def configure(self):
        aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        aggregator.add_result_listener(self)

        self.api_client.set_api_address(self.get_option("api_address"))
        self.task = self.get_option("task", 'dir')
        self.job_name = self.get_option("job_name", 'none')
        self.job_dsc = self.get_option("job_dsc", '')
        self.notify_list = self.get_option("notify", '').split(' ')
        self.version_tested = self.get_option("ver", '')
        self.regression_component = self.get_option("component", '')
        self.is_regression = self.get_option("regress", '0')
        self.logs_basedir = self.get_option("logs_dir", 'logs')
        self.operator = self.get_option("operator", self.operator)

    def check_task_is_open(self, task):
        self.log.debug("Check if task %s is open", task)
        try:
            task_data = self.api_client.get_task_data(task)
        except HTTPError, ex:
            self.log.error("Failed to check task status for '%s': %s", task, ex)
            raise ex
        if  task_data[0]['closed']:
            raise RuntimeError("Task %s is closed: %s" % (task, task_data[0].closed))
        self.log.info("Task %s is ok", task)
        self.task_name = task_data[0]['name']
    
    def prepare_test(self):
        self.check_task_is_open(self.task)

        try:
            console = self.core.get_plugin_of_type(ConsoleOnlinePlugin)
        except Exception, ex:
            self.log.debug("Console not found: %s", ex)
            console = None
            
        if console:    
            console.add_info_widget(JobInfoWidget(self))

    def start_test(self):
        try:
            mon = self.core.get_plugin_of_type(MonitoringPlugin)
        except Exception, ex:
            self.log.debug("Monitoring not found: %s", ex)
            mon = None
            
        if mon and mon.monitoring:    
            mon.monitoring.add_listener(self)
        
        try:
            phantom = self.core.get_plugin_of_type(PhantomPlugin)
            address = phantom.address
            port = phantom.port
            instances = phantom.instances
            tank_type = 1 if phantom.tank_type == 'http' else 2
            ammo_path = phantom.ammo_file
        except Exception, ex:
            self.log.warning("No phantom plugin to get target info: %s", ex)
            address = "127.0.0.1"
            port = 80
            instances = 0
            tank_type = 0
            ammo_path = ''
        
        try: 
            aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
            detailed_field = aggregator.detailed_field
        except Exception, ex:
            self.log.warning("No phantom plugin to get target info: %s", ex)
            detailed_field = "interval_real"

        #TODO: copy old stepper logic to this class            
        loadscheme = self.core.get_option(PhantomPlugin.SECTION, PhantomPlugin.OPTION_SCHEDULE, '')
        loadscheme_expanded = self.core.get_option(PhantomPlugin.SECTION, PhantomPlugin.OPTION_LOADSCHEME, '')         
        loop_count = self.core.get_option(PhantomPlugin.SECTION, PhantomPlugin.OPTION_LOOP_COUNT, '-1')        

        self.jobno = self.api_client.new_job(self.task, self.operator, socket.gethostname(),
                address, port, loadscheme, loadscheme_expanded.split(';'), detailed_field, self.notify_list)
        self.log.info("Web link: %s%s", self.api_client.address, self.jobno)
        self.core.artifacts_dir = self.logs_basedir + '/' + str(self.jobno)
        
        
        self.api_client.edit_job_metainfo(self.jobno,
                self.job_name, self.job_dsc, instances, ammo_path, loop_count,
                self.version_tested, self.is_regression, self.regression_component,
                tank_type, " ".join(sys.argv), 0)
    
    def end_test(self, retcode):
        return retcode
    
    def post_process(self, rc):
        if self.jobno:
            try: 
                self.api_client.close_job(self.jobno, rc)
            except Exception, ex:
                self.log.warning("Failed to close job: %s", ex)
        
            self.log.info("Web link: %s%s", self.api_client.address, self.jobno)
        
            autostop = None
            try:
                autostop = self.core.get_plugin_of_type(AutostopPlugin)
            except Exception, ex:
                self.log.debug("No autostop plugin loaded: %s", ex)
            
            if autostop and autostop.cause_criteria:
                rps = autostop.cause_criteria.cause_second.overall.planned_requests
                if not rps:
                    rps = autostop.cause_criteria.cause_second.overall.RPS
                self.api_client.set_imbalance(self.jobno, rps)
            else:
                self.log.debug("No autostop cause detected")
        return rc    

    def aggregate_second(self, second_aggregate_data):
        """
        @second_aggregate_data: SecondAggregateData
        """
        self.api_client.push_test_data(self.jobno, second_aggregate_data)
    
    def get_sla_by_task(self):
        return self.api_client.get_sla_by_task(self.regression_component)
        
    def monitoring_data(self, data_string):
        self.api_client.push_monitoring_data(self.jobno, data_string)
        
class KSHMAPIClient():
    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.address = None
    
    def set_api_address(self, addr):
        self.address = addr

    def get(self, addr):
        if not self.address:
            raise ValueError("Can't request unknown address")
        
        addr = self.address + addr
        self.log.debug("Making request to: %s", addr)
        req = urllib2.Request(addr)
        resp = urllib2.urlopen(req).read()
        response = json.loads(resp)
        self.log.debug("Response: %s", response)
        return response


    def post_raw(self, addr, json_data):
        if not self.address:
            raise ValueError("Can't request unknown address")

        addr = self.address + addr
        self.log.debug("Making request to: %s => %s", addr, json_data)
        req = urllib2.Request(addr, json_data)
        resp = urllib2.urlopen(req).read()
        self.log.debug("Response: %s", resp)
        return resp
        
    def post(self, addr, data):
        json_data = json.dumps(data)
        resp= self.post_raw(addr, json_data)
        response = json.loads(resp)
        return response
    
    def get_task_data(self, task):
        return self.get("api/task/" + task + "/summary.json")
    
    def new_job(self, task, person, tank, target_host, target_port, loadscheme, loadscheme_expanded, detailed_time, notify_list):
        data = {}
        data['task'] = task
        data['person'] = person
        data['tank'] = tank
        data['host'] = target_host
        data['port'] = target_port
        data['loadscheme'] = loadscheme
        data['loadscheme_expanded'] = loadscheme_expanded
        data['detailed_time'] = detailed_time
        data['notify'] = notify_list
    
        response = self.post("api/job/create.json", data)
        return response[0]['job']
    
    def close_job(self, jobno, rc):
        result = self.get('api/job/' + str(jobno) + '/close.json?exitcode=' + str(rc))
        return result[0]['success']
    
    def edit_job_metainfo(self, jobno, job_name, job_dsc, instances, ammo_path, loop_count, version_tested, is_regression, component, tank_type, cmdline, is_starred):
        data = {}
        data['name'] = job_name
        data['description'] = job_dsc
        data['instances'] = str(instances)
        data['ammo'] = ammo_path
        data['loop'] = loop_count
        data['version'] = version_tested
        data['regression'] = str(is_regression)
        data['component'] = component
        data['tank_type'] = int(tank_type)
        data['command_line'] = cmdline
        data['starred'] = int(is_starred)

        response = self.post('api/job/' + str(jobno) + '/edit.json', data)
        return response


    def set_imbalance(self, jobno, rps):
        data = {'imbalance': rps}
        response = self.post('api/job/' + str(jobno) + '/edit.json', data)
        return response
    
    
    def second_data_to_push_item(self, data):
        """
        @data: SecondAggregateDataItem
        """
        api_data = {
                'overall': data.overall,
                'case': data.case,
                'net_codes': [],
                'http_codes': [],
                'time_intervals': [],
        }
        
        self.log.debug("selfload: %s", data.selfload)
        
        api_data['trail'] = {
                    'time': str(data.time),
                    'reqps': int(data.planned_requests),
                    'resps': int(data.RPS),
                    'expect': float(data.avg_response_time),
                    'disper': float(data.dispersion),
                    'self_load': float(data.selfload),
                    'input': int(data.input),
                    'output': int(data.output),
                    'q50': float(data.quantiles['50']),
                    'q75': float(data.quantiles['75']),
                    'q80': float(data.quantiles['80']),
                    'q85': float(data.quantiles['85']),
                    'q90': float(data.quantiles['90']),
                    'q95': float(data.quantiles['95']),
                    'q98': float(data.quantiles['98']),
                    'q99': float(data.quantiles['99']),
                    'q100': float(data.quantiles['100']),
                    'connect_time': float(data.avg_connect_time),
                    'send_time': float(data.avg_send_time),
                    'latency': float(data.avg_latency),
                    'receive_time': float(data.avg_receive_time),
                    'threads': int(data.active_threads),
                }

        for code, cnt in data.net_codes.iteritems():
            api_data['net_codes'].append({'code': int(code), 'count': int(cnt)})  

        for code, cnt in data.http_codes.iteritems():
            api_data['http_codes'].append({'code': int(code), 'count': int(cnt)})  

        api_data['time_intervals'] = data.times_dist       
        return api_data
    
    
    def push_test_data(self, jobno, data):
        uri = 'api/job/' + str(jobno) + '/push_data.json'
        for case in data.cases.values():
            case_data = self.second_data_to_push_item(case)
            self.post(uri, case_data)
        overall = self.second_data_to_push_item(data.overall)
        try:
            self.post(uri, overall)
        except Exception, e:
            self.log.warn("Failed to push second data to API, retry in 30 sec: %s", e)
            time.sleep(30)
            self.post(uri, overall)
            
            
    def get_sla_by_task(self, component):
        if not component or component == '0':
            self.log.debug("Skip SLA get")
            return []
        
        self.log.debug("Requesting SLA for component %s", component)
        response = self.get('api/regress/' + component + '/slalist.json')
        
        sla = []
        for sla_item in response:
            sla.append((sla_item['prcnt'], sla_item['time']))
    
        return sla                

    def push_monitoring_data(self, jobno, send_data):
        if send_data:
            addr = "api/monitoring/receiver/push?job_id=%s" % jobno
            try:
                self.post_raw(addr, send_data)
            except HTTPError, ex:
                self.log.warning('Problems sending monitoring data, retry in 30s: %s', ex)
                time.sleep(30)
                self.post_raw(addr, send_data)
    

class JobInfoWidget(AbstractInfoWidget):
    def __init__(self, sender):
        AbstractInfoWidget.__init__(self)
        self.owner = sender        
    
    def get_index(self):
        return 1

    def render(self, screen):        
        template = "Author: " + screen.markup.RED + "%s" + screen.markup.RESET + "%s\n   Job: %s %s\n  Task: %s %s\n   Web: %s%s"
        data = (self.owner.operator[:1], self.owner.operator[1:], self.owner.jobno, self.owner.job_name, self.owner.task, self.owner.task_name, self.owner.api_client.address, self.owner.jobno)
        
        return template % data