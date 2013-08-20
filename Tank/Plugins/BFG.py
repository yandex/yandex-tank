''' Generic native load generator '''
from Tank.Plugins.Aggregator import AggregatorPlugin, AbstractReader
from Tank.Plugins.ConsoleOnline import ConsoleOnlinePlugin, AbstractInfoWidget
from tankcore import AbstractPlugin
from Queue import Queue
import logging
import time
from threading import Timer
from Tank.stepper import StepperWrapper, StpdReader
from collections import namedtuple
import os
import socket
import datetime

Sample = namedtuple('Sample', 'marker,threads,overallRT,httpCode,netCode,sent,received,connect,send,latency,receive,accuracy')

class BFGPlugin(AbstractPlugin):

    ''' JMeter tank plugin '''
    SECTION = 'bfg'

    def __init__(self, core):
        self.log = logging.getLogger(__name__)
        AbstractPlugin.__init__(self, core)
        self.gun_type = None
        self.start_time = time.time()
        self.stepper_wrapper = StepperWrapper(self.core, BFGPlugin.SECTION)
        self.log.info("Initialized BFG")

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        return ["gun_type", "instances"] + self.stepper_wrapper.get_available_options

    def configure(self):
        self.log.info("Configuring BFG...")
        self.stepper_wrapper.read_config()

    def prepare_test(self):
        self.stepper_wrapper.prepare_stepper()
        self.bfg = BFG(
            gun_type=self.get_option("gun_type"),
            instances=self.get_option("instances", '15'),
            stpd_filename=self.stepper_wrapper.stpd,
        )
        aggregator = None
        try:
            aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        except Exception, ex:
            self.log.warning("No aggregator found: %s", ex)

        if aggregator:
            aggregator.reader = BFGReader(aggregator, self.bfg)
            pass

        try:
            console = self.core.get_plugin_of_type(ConsoleOnlinePlugin)
        except Exception, ex:
            self.log.debug("Console not found: %s", ex)
            console = None

        if console:
            widget = BFGInfoWidget(self)
            console.add_info_widget(widget)
            if aggregator:
                aggregator.add_result_listener(widget)
            pass
        self.log.info("Prepared BFG")

    def start_test(self):
        self.log.info("Starting BFG")
        # TODO: start BFG here
        self.start_time = time.time()
        self.bfg.start()

    def is_test_finished(self):
        if self.bfg.running:
            return -1
        else:
            retcode = self.bfg.retcode
            self.log.info(
                "BFG finished with exit code: %s", retcode)
            return retcode

    def end_test(self, retcode):
        if self.bfg.running:
            self.log.info("Terminating BFG")
            self.bfg.stop()
        return retcode

class BFGInfoWidget(AbstractInfoWidget):
    ''' Console widget '''    
    def __init__(self, bfg):
        AbstractInfoWidget.__init__(self)
        self.bfg = bfg
        self.active_threads = 0

    def get_index(self):
        return 0

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


    def render(self, screen):        
        res = ''
        info = self.owner.get_info()
        if self.owner.phantom:
            template = "Hosts: %s => %s:%s\n Ammo: %s\nCount: %s\n Load: %s"
            data = (socket.gethostname(), info.address, info.port, os.path.basename(info.ammo_file), self.ammo_count, ' '.join(info.rps_schedule))
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
        if self.time_lag > self.owner.buffered_seconds * 5:
            self.log.debug("Time lag: %s", self.time_lag)
            res += screen.markup.RED + str(datetime.timedelta(seconds=self.time_lag)) + screen.markup.RESET
        elif self.time_lag > self.owner.buffered_seconds:
            res += screen.markup.YELLOW + str(datetime.timedelta(seconds=self.time_lag)) + screen.markup.RESET
        else:
            res += str(datetime.timedelta(seconds=self.time_lag))
                
        return res


class BFGReader(AbstractReader):

    '''
    Listens results from BFG and provides them to Aggregator
    '''

    def __init__(self, aggregator, bfg):
        AbstractReader.__init__(self, aggregator)
        bfg.add_listener(self)

    def get_next_sample(self, force):
        if self.data_queue:
            return self.pop_second()
        else:
            return None

    def send(self, cur_time, sample):
        if not cur_time in self.data_buffer.keys():
            self.data_queue.append(cur_time)
            self.data_buffer[cur_time] = []
        self.data_buffer[cur_time].append(list(sample))


class BFG(object):

    def __init__(
        self,
        gun_type,
        instances,
        stpd_filename,
    ):
        self.log = logging.getLogger(__name__)
        self.log.info(
            "BFG using gun '%s', stpd from %s", gun_type, stpd_filename)
        guns = {
            'log': LogGun,
        }
        if gun_type in guns:
            self.gun = guns[gun_type]()
        else:
            raise NotImplementedError(
                'No such gun type implemented: "%s"' % gun_type)
        self.stpd_filename = stpd_filename
        self.instances = int(instances)
        self.running = False
        self.retcode = None
        self.ammo_cache = Queue(self.instances)
        self.listeners = []

    def add_listener(self, l):
        self.listeners.append(l)

    def start(self):
        self.running = True
        self.start_time = time.time()
        stpd = StpdReader(self.stpd_filename)
        self.tasks = [self.schedule(*element) for element in stpd]
        [task.join() for task in self.tasks]
        self.stop()

    def schedule(self, timestamp, missile, marker):
        delay = timestamp / 1000.0 - (time.time() - self.start_time)
        timer_task = Timer(delay, self._shoot, [missile, marker])
        timer_task.start()
        return timer_task

    def _shoot(self, missile, marker):
        cur_time, sample = self.gun.shoot(missile, marker)
        for l in self.listeners:
            l.send(cur_time, sample)

    def stop(self):
        self.running = False
        self.retcode = 0
        if self.tasks and len(self.tasks):
            [task.cancel() for task in self.tasks]


class LogGun(object):

    def __init__(self):
        self.log = logging.getLogger(__name__)

    def shoot(self, missile, marker):
        self.log.debug("Missile: %s\n%s", marker, missile)
        data_item = Sample(
            marker,  # marker
            1,       # threads
            120,     # overallRT
            0,       # httpCode
            0,       # netCode
            0,       # sent
            0,       # received
            0,       # connect
            0,       # send
            120,     # latency
            0,       # receive
            0,       # accuracy
        )
        return (int(time.time()), data_item)
