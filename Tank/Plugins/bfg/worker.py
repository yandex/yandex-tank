import logging
import time
from Tank.stepper import StpdReader
import multiprocessing as mp
import threading as th
import signal
from Queue import Empty, Full

def signal_handler(signum, frame):
    pass

class BFG(object):

    def __init__(
        self,
        gun,
        instances,
        threads,
        stpd_filename,
        cached_stpd=False,
    ):
        self.log = logging.getLogger(__name__)
        self.log.info(
            "BFG using stpd from %s", stpd_filename)
        self.gun = gun
        self.stpd_filename = stpd_filename
        self.instances = int(instances)
        self.threads = int(threads)
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
        # disable signal handler from parent:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        self.start_time = time.time()
        shooter = BFGShooter(
            self.gun,
            results,
            stpd_filename=self.stpd_filename,
            threads=self.threads,
            instances=self.instances,
            cached_stpd=self.cached_stpd,
        )
        try:
            shooter.start()
        except (KeyboardInterrupt, SystemExit):
            shooter.stop()

        self.log.info("Waiting for shooter")
        shooter.join()
        self.log.info("Shooter exited")


class BFGShooter(object):
    def __init__(self, gun, results, stpd_filename, instances=10, threads=10, cached_stpd=False):
        self.log = logging.getLogger(__name__)
        self.gun = gun
        self.threads = threads
        self.results = results
        self.quit = mp.Event()
        self.task_queue = mp.Queue(1024)
        self.cached_stpd = cached_stpd
        self.stpd_filename = stpd_filename
        self.pool = [mp.Process(target=self._worker) for i in xrange(0, instances)]
        self.feeder = th.Thread(target=self._feed)

    def start(self):
        self.start_time = time.time()
        map(lambda x: x.start(), self.pool)
        self.feeder.start()

    def stop(self):
        self.quit.set()

    def join(self):
        try:
            self.log.info("Waiting for workers")
            map(lambda x: x.join(), self.pool)
            self.log.info("All workers exited.")
        except (KeyboardInterrupt, SystemExit):
            self.quit.set()

    def _feed(self):
        plan = StpdReader(self.stpd_filename)
        if self.cached_stpd:
            plan = list(plan)
        for task in plan:
            if self.quit.is_set():
                self.log.info("Stop feeding: gonna quit")
                return
            self.task_queue.put(task)
        self.log.info("Feeded all data. Set quit marker")
        self.quit.set()

    def _worker(self):
        self.log.info("Started shooter process with %s threads..." % self.threads)
        pool = [mp.Process(target=self._thread_worker) for i in xrange(0, self.threads)]
        map(lambda x: x.start(), pool)
        map(lambda x: x.join(), pool)
        self.log.info("Exiting shooter process...")

    def _thread_worker(self):
        self.log.debug("Starting shooter thread...")
        while not self.quit.is_set():
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
                self.quit.set()
            except Empty:
                self.log.info("Empty queue. Quit flag is %s" % self.quit.is_set())
                pass
            except Full:
                self.log.warning("Couldn't put to result queue because it's full")
        self.log.debug("Exiting shooter thread...")
