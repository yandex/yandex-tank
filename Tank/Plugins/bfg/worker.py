import logging
import time
from Tank.stepper import StpdReader
import multiprocessing as mp
import threading as th

class BFG(object):

    def __init__(
        self,
        gun,
        instances,
        stpd_filename,
    ):
        self.log = logging.getLogger(__name__)
        self.log.info(
            "BFG using stpd from %s", stpd_filename)
        self.gun = gun
        self.stpd_filename = stpd_filename
        self.instances = int(instances)
        self.results = None
        self.worker = None

    def start(self):
        results = mp.Queue()
        self.worker = mp.Process(target=self._start, args=(results,))
        self.worker.start()
        self.results = results

    def _start(self, result_queue):
        '''
        Worker that runs as a separate process
        '''
        self.results = result_queue
        self.start_time = time.time()
        stpd = StpdReader(self.stpd_filename)
        shooter = BFGShooter(self.gun, result_queue, instances = self.instances)
        self.tasks = [
            shooter.shoot(self.start_time + (ts / 1000.0), missile, marker)
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

    def __init__(self, gun, result_queue, instances = 10):
        self.gun = gun
        self.result_queue = result_queue
        self.instances = instances

    def shoot(self, planned_time, missile, marker):
        delay = planned_time - time.time()
        while th.active_count() >= self.instances:
            if delay - delay / 2 > 0:
                time.sleep(delay - delay / 2)
                delay = planned_time - time.time()
        task = th.Timer(delay, self._shoot, [missile, marker])
        task.start()
        return task

    def _shoot(self, missile, marker):
        cur_time, sample = self.gun.shoot(missile, marker)
        self.result_queue.put((cur_time, sample))
