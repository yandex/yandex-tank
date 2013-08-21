''' Generic native load generator '''
from Tank.Plugins.Aggregator import AggregatorPlugin, AbstractReader
from Tank.Plugins.ConsoleOnline import ConsoleOnlinePlugin, AbstractInfoWidget
from tankcore import AbstractPlugin
import logging
import time
from threading import Timer
from multiprocessing import Process, Queue
from Tank.stepper import StepperWrapper, StpdReader
from collections import namedtuple
import datetime
from random import randint

Sample = namedtuple(
    'Sample', 'marker,threads,overallRT,httpCode,netCode,sent,received,connect,send,latency,receive,accuracy')


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
            widget = BFGInfoWidget()
            console.add_info_widget(widget)
            if aggregator:
                aggregator.add_result_listener(widget)
            pass
        self.log.info("Prepared BFG")

    def start_test(self):
        self.log.info("Starting BFG")
        self.start_time = time.time()
        self.bfg.start()

    def is_test_finished(self):
        if self.bfg.running():
            return -1
        else:
            self.log.info("BFG finished")
            return 0

    def end_test(self, retcode):
        if self.bfg.running():
            self.log.info("Terminating BFG")
            self.bfg.stop()
        return retcode


class BFGInfoWidget(AbstractInfoWidget):

    ''' Console widget '''

    def __init__(self):
        AbstractInfoWidget.__init__(self)
        self.active_threads = 0
        self.instances = 0
        self.planned = 0
        self.RPS = 0
        self.selfload = 0
        self.time_lag = 0
        self.planned_rps_duration = 0

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
        self.time_lag = int(
            time.time() - time.mktime(second_aggregate_data.time.timetuple()))

    def render(self, screen):
        res = ''

        res += "Active instances: "
        res += str(self.instances)

        res += "\nPlanned requests: %s for %s\nActual responses: " % (
            self.planned, datetime.timedelta(seconds=self.planned_rps_duration))
        if not self.planned == self.RPS:
            res += screen.markup.YELLOW + str(self.RPS) + screen.markup.RESET
        else:
            res += str(self.RPS)

        res += "\n        Accuracy: "
        if self.selfload < 80:
            res += screen.markup.RED + \
                ('%.2f' % self.selfload) + screen.markup.RESET
        elif self.selfload < 95:
            res += screen.markup.YELLOW + \
                ('%.2f' % self.selfload) + screen.markup.RESET
        else:
            res += ('%.2f' % self.selfload)

        res += "%\n        Time lag: "
        res += str(datetime.timedelta(seconds=self.time_lag))

        return res


class BFGReader(AbstractReader):

    '''
    Listens results from BFG and provides them to Aggregator
    '''

    def __init__(self, aggregator, bfg):
        AbstractReader.__init__(self, aggregator)
        self.bfg = bfg

    def get_next_sample(self, force):
        new_data = []
        while not self.bfg.results.empty():
            new_data.append(self.bfg.results.get())
        for cur_time, sample in new_data:
            if not cur_time in self.data_buffer.keys():
                self.data_queue.append(cur_time)
                self.data_buffer[cur_time] = []
            self.data_buffer[cur_time].append(list(sample))
        if self.data_queue:
            return self.pop_second()
        else:
            return None


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
        self.results = None
        self.worker = None

    def start(self):
        self.results = Queue()
        self.worker = Process(target=self._start, args=(self.results,))
        self.worker.start()


    def _start(self, result_queue):
        self.results = result_queue
        self.start_time = time.time()
        stpd = StpdReader(self.stpd_filename)
        shooter = BFGShooter(self.gun, result_queue)
        self.tasks = [
            shooter.shoot(self.start_time + (ts / 1000.0),missile, marker)
            for ts, missile, marker in stpd
        ]
        try:
            [task.join() for task in self.tasks]
        except KeyboardInterrupt:
            [task.cancel() for task in self.tasks]

    def running(self):
        if self.worker:
            return self.worker.is_alive()
        else:
            return False

    def stop(self):
        if self.worker:
            return self.worker.terminate()


class BFGShooter(object):
    '''
    Executes tasks from queue at a specified time
    (or immediately if time is in the past).
    The results of execution are added to result_queue.
    '''
    def __init__(self, gun, result_queue):
        self.gun = gun
        self.result_queue = result_queue

    def shoot(self, planned_time, missile, marker):
        delay = planned_time - time.time()
        task = Timer(delay, self._shoot, [missile, marker])
        task.start()
        return task

    def _shoot(self, missile, marker):
        cur_time, sample = self.gun.shoot(missile, marker)
        self.result_queue.put((cur_time, sample))


class LogGun(object):

    def __init__(self):
        self.log = logging.getLogger(__name__)

    def shoot(self, missile, marker):
        self.log.debug("Missile: %s\n%s", marker, missile)
        rt = randint(2, 30000)
        data_item = Sample(
            marker,  # marker
            1,       # threads
            rt,      # overallRT
            0,       # httpCode
            0,       # netCode
            0,       # sent
            0,       # received
            0,       # connect
            0,       # send
            rt,      # latency
            0,       # receive
            0,       # accuracy
        )
        return (int(time.time()), data_item)
