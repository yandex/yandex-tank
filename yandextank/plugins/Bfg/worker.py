import logging
import time
from yandextank.stepper import StpdReader
import multiprocessing as mp
import threading as th
from queue import Empty, Full

from contextlib import contextmanager

logger = logging.getLogger(__name__)


def signal_handler(signum, frame):
    pass


class InstanceCounter(object):
    def __init__(self):
        self._v = mp.Value('i', 0)
        self._lock = mp.Lock()

    def inc(self):
        with self._lock:
            self._v.value += 1

    def dec(self):
        with self._lock:
            self._v.value -= 1

    @contextmanager
    def context(self):
        self.inc()
        yield
        self.dec()

    def get(self):
        with self._lock:
            return self._v.value


class BFG(object):
    """
    A BFG load generator that manages multiple workers as processes and
    threads in each of them and feeds them with tasks
    """

    def __init__(self, gun, instances, stpd_filename, cached_stpd=False):
        logger.info("""
BFG using stpd from {stpd_filename}
Instances: {instances}
Gun: {gun.__class__.__name__}
""".format(stpd_filename=stpd_filename,
           instances=instances,
           gun=gun, ))
        self.instances = int(instances)
        self.instance_counter = InstanceCounter()
        self.results = mp.Queue()
        self.gun = gun
        self.gun.results = self.results
        self.quit = mp.Event()
        self.task_queue = mp.Queue(1024)
        self.cached_stpd = cached_stpd
        self.stpd_filename = stpd_filename
        self.pool = [
            mp.Process(target=self._worker) for _ in xrange(0, self.instances)
        ]
        self.feeder = th.Thread(target=self._feed, name="Feeder")
        self.workers_finished = False

    def start(self):
        self.start_time = time.time()
        for process in self.pool:
            process.daemon = True
            process.start()
        self.feeder.start()

    def running(self):
        """
        True while there are alive workers out there. Tank
        will quit when this would become False
        """
        return not self.workers_finished

    def stop(self):
        """
        Say the workers to finish their jobs and quit.
        """
        self.quit.set()

    def _feed(self):
        """
        A feeder that runs in distinct thread in main process.
        """
        self.plan = StpdReader(self.stpd_filename)
        if self.cached_stpd:
            self.plan = list(self.plan)
        for task in self.plan:
            if self.quit.is_set():
                logger.info("Stop feeding: gonna quit")
                return
            # try putting a task to a queue unless there is a quit flag
            # or all workers have exited
            while 1:
                try:
                    self.task_queue.put(task, timeout=1)
                    break
                except Full:
                    if self.quit.is_set() or self.workers_finished:
                        return
                    else:
                        continue
        workers_count = self.instances
        logger.info("Feeded all data. Publishing %d killer tasks" %
                    (workers_count))
        retry_delay = 1
        for _ in range(5):
            try:
                [self.task_queue.put(None,
                                     timeout=1)
                 for _ in xrange(0, workers_count)]
                break
            except Full:
                logger.debug("Couldn't post killer tasks"
                             " because queue is full. Retrying in %ss",
                             retry_delay)
                time.sleep(retry_delay)
                retry_delay *= 2

        try:
            logger.info("Waiting for workers")
            map(lambda x: x.join(), self.pool)
            logger.info("All workers exited.")
            self.workers_finished = True
        except (KeyboardInterrupt, SystemExit):
            self.task_queue.close()
            self.results.close()
            self.quit.set()
            logger.info("Going to quit. Waiting for workers")
            map(lambda x: x.join(), self.pool)
            self.workers_finished = True

    def _worker(self):
        """
        A worker that does actual jobs
        """
        logger.debug("Init shooter process")
        try:
            self.gun.init()
        except Exception:
            logger.exception("Couldn't initialize gun. Exit shooter process")
            return
        while not self.quit.is_set():
            try:
                task = self.task_queue.get(timeout=1)
                if not task:
                    logger.debug("Got killer task.")
                    break
                timestamp, missile, marker = task
                planned_time = self.start_time + (timestamp / 1000.0)
                delay = planned_time - time.time()
                if delay > 0:
                    time.sleep(delay)
                with self.instance_counter.context():
                    self.gun.shoot(missile, marker)
            except (KeyboardInterrupt, SystemExit):
                break
            except Empty:
                if self.quit.is_set():
                    logger.debug("Empty queue. Exiting process")
                    return
            except Full:
                logger.warning(
                    "Couldn't put to result queue because it's full")
            except Exception:
                logger.exception("Bfg shoot exception")

        logger.debug("Exit shooter process")
