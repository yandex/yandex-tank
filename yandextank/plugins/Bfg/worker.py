import logging
import time
import threading as th
import multiprocessing as mp
from queue import Empty, Full

from ...stepper import StpdReader

logger = logging.getLogger(__name__)


class BFGBase(object):
    """
    A BFG load generator that manages multiple workers as processes and
    threads in each of them and feeds them with tasks
    """

    def __init__(self, gun, instances, stpd_filename, cached_stpd=False,
                 green_threads_per_instance=None):
        logger.info(
            """
BFG using stpd from {stpd_filename}
Instances: {instances}
Gun: {gun.__class__.__name__}
""".format(
                stpd_filename=stpd_filename,
                instances=instances,
                gun=gun, ))
        self.instances = int(instances)
        self.instance_counter = mp.Value('i')
        self.results = mp.Queue(16384)
        self.gun = gun
        self.gun.results = self.results
        self.quit = mp.Event()
        self.task_queue = mp.Queue(1024)
        self.cached_stpd = cached_stpd
        self.stpd_filename = stpd_filename
        self.pool = [
            mp.Process(target=self._worker) for _ in range(self.instances)
        ]
        self.feeder = th.Thread(target=self._feed, name="Feeder")
        self.feeder.daemon = True
        self.workers_finished = False
        self.start_time = None
        self.plan = None
        self.green_threads_per_instance = green_threads_per_instance

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
        # yapf:disable
        while sorted([
                self.pool[i].is_alive()
                for i in range(len(self.pool))])[-1]:
            time.sleep(1)
        # yapf:enable
        try:
            while not self.task_queue.empty():
                self.task_queue.get(timeout=0.1)
            self.task_queue.close()
            self.feeder.join()
        except Exception as ex:
            logger.info(ex)

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
            while True:
                try:
                    self.task_queue.put(task, timeout=1)
                    break
                except Full:
                    if self.quit.is_set() or self.workers_finished:
                        return
                    else:
                        continue
        workers_count = self.instances
        logger.info(
            "Feeded all data. Publishing %d killer tasks" % (workers_count))
        retry_delay = 1
        for _ in range(5):
            try:
                [
                    self.task_queue.put(None, timeout=1)
                    for _ in range(0, workers_count)
                ]
                break
            except Full:
                logger.debug(
                    "Couldn't post killer tasks"
                    " because queue is full. Retrying in %ss", retry_delay)
                time.sleep(retry_delay)
                retry_delay *= 2

        try:
            logger.info("Waiting for workers")
            for x in self.pool:
                x.join()
            logger.info("All workers exited.")
            self.workers_finished = True
        except (KeyboardInterrupt, SystemExit):
            self.task_queue.close()
            self.results.close()
            self.quit.set()
            logger.info("Going to quit. Waiting for workers")
            for x in self.pool:
                x.join()
            self.workers_finished = True


class BFGMultiprocessing(BFGBase):
    """
    Default worker type, creates process per worker,
    every process executes requests synchronously inside.
    """
    def _worker(self):
        """
        A worker that does actual jobs
        """
        logger.debug("Init shooter process")
        try:
            self.gun.setup()
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

                try:
                    with self.instance_counter.get_lock():
                        self.instance_counter.value += 1
                    self.gun.shoot(missile.decode('utf8'), marker)
                finally:
                    with self.instance_counter.get_lock():
                        self.instance_counter.value -= 1

            except (KeyboardInterrupt, SystemExit):
                break
            except Empty:
                if self.quit.is_set():
                    logger.debug("Empty queue. Exiting process")
                    return
            except Full:
                logger.warning("Couldn't put to result queue because it's full")
            except Exception:
                logger.exception("Bfg shoot exception")

        try:
            self.gun.teardown()
        except Exception:
            logger.exception("Couldn't finalize gun. Exit shooter process")
            return
        logger.debug("Exit shooter process")


class BFGGreen(BFGBase):
    """
    Green version of the worker. Starts `self.instances` processes,
    each of process has a pool of `self.green_threads_per_instance` green threads.
    """
    def _worker(self):
        from gevent import monkey, spawn
        from gevent.queue import Queue as GreenQueue
        # NOTE: Patching everything will conflict with multiprocessing
        monkey.patch_all(thread=False, select=False)

        logger.debug("Init shooter process")
        try:
            self.gun.setup()
        except Exception:
            logger.exception("Couldn't initialize gun. Exit shooter process")
            return

        self.green_queue = GreenQueue(self.green_threads_per_instance)
        self.green_pool = [spawn(self._green_worker) for _ in range(0, self.green_threads_per_instance)]

        # Keep track of tasks sent to greenlets. If all greenlets are busy -
        # don't pull more tasks from the main queue, let other workers do that.
        self._free_threads_count = self.green_threads_per_instance

        while not self.quit.is_set():
            while not self.task_queue.empty() and self._free_threads_count:
                try:
                    task = self.task_queue.get_nowait()
                except Empty:
                    continue

                self._free_threads_count -= 1

                if not task:
                    logger.debug("Got killer task.")
                    self.quit.set()
                    break

                self.green_queue.put(task)

            time.sleep(0.1)

        for g in self.green_pool:
            g.join()

        try:
            self.gun.teardown()
        except Exception:
            logger.exception("Couldn't finalize gun. Exit shooter process")
            return
        logger.debug("Exit shooter process")

    def _green_worker(self):
        """
        A worker that does actual jobs
        """
        while not self.quit.is_set():
            try:
                task = self.green_queue.get(timeout=1)

                timestamp, missile, marker = task
                planned_time = self.start_time + (timestamp / 1000.0)
                delay = planned_time - time.time()

                if delay > 0:
                    time.sleep(delay)

                try:
                    with self.instance_counter.get_lock():
                        self.instance_counter.value += 1

                    self.gun.shoot(missile.decode('utf8'), marker)
                finally:
                    with self.instance_counter.get_lock():
                        self.instance_counter.value -= 1

                    self._free_threads_count += 1

            except (KeyboardInterrupt, SystemExit):
                break
            except Empty:
                continue
            except Full:
                logger.warning("Couldn't put to result queue because it's full")
            except Exception:
                logger.exception("Bfg shoot exception")
