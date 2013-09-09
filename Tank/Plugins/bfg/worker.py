import logging
import time
from Tank.stepper import StpdReader
import multiprocessing as mp
import threading as th
from Queue import Queue

class BFG(object):

    def __init__(
        self,
        gun,
        instances,
        stpd_filename,
        cached_stpd=False,
    ):
        self.log = logging.getLogger(__name__)
        self.log.info(
            "BFG using stpd from %s", stpd_filename)
        self.gun = gun
        self.stpd_filename = stpd_filename
        self.instances = int(instances)
        self.results = None
        self.worker = None
        self.cached_stpd = cached_stpd

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
        if self.cached_stpd:
            stpd = list(stpd)
        shooter = BFGShooter(self.gun, result_queue, instances = self.instances)
        shooter.start()
        try:
            for ts, missile, marker in stpd:
                shooter.shoot(self.start_time + (ts / 1000.0), missile, marker)
            shooter.finish()
        except KeyboardInterrupt:
            shooter.finish()

    def running(self):
        if self.worker:
            return self.worker.is_alive()
        else:
            return False

    def stop(self):
        if self.worker:
            return self.worker.terminate()


class BFGShooter(object):
    def __init__(self, gun, result_queue, instances = 10):
        self.gun = gun
        self.result_queue = result_queue
        self.quit = False
        self.missile_queue = Queue()
        self.thread_pool = [th.Thread(target=self._worker) for i in xrange(0, instances)]

    def start(self):
        map(lambda x: x.start(), self.thread_pool)

    def finish(self):
        self.quit = True
        [thread.join for thread in self.thread_pool]

    def shoot(self, planned_time, missile, marker):
        delay = planned_time - time.time()
        if delay > 0:
            time.sleep(delay)
        self._shoot(missile, marker)

    def _shoot(self, missile, marker):
        self.missile_queue.put((missile, marker))

    def _worker(self):
        while not self.quit:
            missile, marker = self.missile_queue.get()
            cur_time, sample = self.gun.shoot(missile, marker)
            self.result_queue.put((cur_time, sample))
