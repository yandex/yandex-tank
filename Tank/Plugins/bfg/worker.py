import logging
import time
from Tank.stepper import StpdReader
import multiprocessing as mp
import threading as th
from Queue import Empty, Full

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

    def running(self):
        if self.worker:
            return self.worker.is_alive()
        else:
            return False

    def stop(self):
        if self.worker:
            return self.worker.terminate()

    def _start(self, results):
        '''
        Worker that runs as a separate process
        '''
        self.start_time = time.time()
        stpd = StpdReader(self.stpd_filename)
        if self.cached_stpd:
            stpd = list(stpd)
        self.shooter = BFGShooter(
            self.gun,
            results,
            plan=stpd,
            instances=self.instances
        )
        try:
            self.shooter.start()
        except (KeyboardInterrupt, SystemExit):
            self.shooter.stop()
            self.shooter.join()


class BFGShooter(object):
    def __init__(self, gun, results, plan, instances = 10):
        self.log = logging.getLogger(__name__)
        self.gun = gun
        self.results = results
        self.quit = mp.Value('b')
        self.quit.value = False
        self.task_queue = mp.Queue()
        self.plan = plan
        self.pool = [mp.Process(target=self._worker) for i in xrange(0, instances)]
        self.feeder = th.Thread(target=self._feed)

    def start(self):
        self.start_time = time.time()
        map(lambda x: x.start(), self.pool)
        self.feeder.start()

    def stop(self):
        self.quit.value = True

    def join(self):
        #self.feeder.join()
        #self.log.info("Feeder have just exited")
        map(lambda x: x.join(), self.pool)

    def _feed(self):
        for task in self.plan:
            if self.quit.value:
                break
            self.task_queue.put(task)
        self.log.info("Feeded all data. Set quit marker")
        self.quit.value = True

    def _worker(self):
        while not self.quit.value:
            try:
                task = self.task_queue.get(timeout=1)
                ts, missile, marker = task
                planned_time = self.start_time + (ts / 1000.0)
                delay = planned_time - time.time()
                if delay > 0:
                    time.sleep(delay)
                cur_time, sample = self.gun.shoot(missile, marker)
                self.results.put((cur_time, sample), timeout=1)
            except (KeyboardInterrupt, SystemExit):
                self.quit.value = True
            except Empty:
                self.log.info("Empty queue. Quit = %s" % self.quit.value)
                pass
            except Full:
                self.log.warning("Couldn't put to result queue because it's full")
        self.log.info("Exiting worker...")
        return
