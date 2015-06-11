import logging
import time
from yandextank.stepper import StpdReader
from .zmq_reader import ZmqReader
import multiprocessing as mp
import threading as th
from Queue import Empty, Full

def signal_handler(signum, frame):
    pass


class BFG(object):
    def __init__(self, gun, instances, threads, stpd_filename, zmq=False, cached_stpd=False):
        self.log = logging.getLogger(__name__)
        self.log.info(
            """
BFG using stpd from {stpd_filename}
Instances: {instances}
Threads per instance: {threads}
Gun: {gun.__class__}
""".format(
            stpd_filename=stpd_filename,
            instances=instances,
            threads=threads,
            gun=gun,
        ))
        self.gun = gun
        self.instances = int(instances)
        self.threads = int(threads)
        self.results = mp.Queue(16384)
        self.quit = mp.Event()
        self.task_queue = mp.Queue(1024)
        self.cached_stpd = cached_stpd
        self.stpd_filename = stpd_filename
        self.pool = [
            mp.Process(target=self._worker) for _ in xrange(0, self.instances)]
        self.feeder = th.Thread(target=self._feed, name="Feeder")
        self.zmq = zmq
        self.workers_finished = False

    def start(self):
        self.start_time = time.time()
        for process in self.pool:
            process.daemon = True
            process.start()
        self.feeder.start()

    def running(self):
        return not self.workers_finished

    def stop(self):
        self.quit.set()
        self.plan.stop()

    def _feed(self):
        if self.zmq:
            print "Starting ZMQ: connecting to ", self.zmq
            self.plan = ZmqReader(self.zmq)
        else:
            self.plan = StpdReader(self.stpd_filename)
            if self.cached_stpd:
                self.plan = list(self.plan)
        for task in self.plan:
            if self.quit.is_set():
                self.log.info("Stop feeding: gonna quit")
                # self.task_queue.close()
                return
            while 1:
                try:
                    self.log.info(task)
                    self.task_queue.put(task, timeout=1)
                except Full:
                    if self.quit.is_set() or self.workers_finished:
                        return
        self.log.info(
            "Feeded all data. Publishing %d killer tasks" % (
                self.threads * self.instances))
        [self.task_queue.put(None, timeout=1) for _ in xrange(
            0, self.threads * self.instances)]

        try:
            self.log.info("Waiting for workers")
            map(lambda x: x.join(), self.pool)
            self.log.info("All workers exited.")
            self.workers_finished = True
        except (KeyboardInterrupt, SystemExit):
            self.quit.set()
            # self.task_queue.close()
            self.log.info("Waiting for workers")
            map(lambda x: x.join(), self.pool)
            self.workers_finished = True


    def _worker(self):
        self.log.info(
            "Started shooter process with %s threads..." % self.threads)
        pool = [th.Thread(
                target=self._thread_worker) for _ in xrange(0, self.threads)]
        map(lambda x: x.start(), pool)
        try:
            map(lambda x: x.join(), pool)
            self.log.info("Exiting shooter process...")
        except (KeyboardInterrupt, SystemExit):
            self.quit.set()

    def _thread_worker(self):
        self.log.info("Starting shooter thread %s", th.current_thread().name)
        while not self.quit.is_set():
            try:
                task = self.task_queue.get(timeout=1)
                if not task:
                    self.log.info("%s got killer task.", th.current_thread().name)
                    break
                timestamp, missile, marker = task
                planned_time = self.start_time + (timestamp / 1000.0)
                delay = planned_time - time.time()
                if delay > 0:
                    time.sleep(delay)
                self.gun.shoot(missile, marker, self.results)
            except (KeyboardInterrupt, SystemExit):
                self.quit.set()
            except Empty:
                if self.quit.is_set():
                    self.log.info("Empty queue. Exiting thread %s", th.current_thread().name)
                    return
            except Full:
                self.log.warning(
                    "Couldn't put to result queue because it's full")
        self.log.info("Exiting shooter thread %s", th.current_thread().name)
