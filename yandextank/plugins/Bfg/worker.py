import logging
import time
import threading as th
import multiprocessing as mp
import signal
from queue import Empty, Full
import os

from ...stepper import StpdReader
from .guns import MeasureCounterGun

logger = logging.getLogger(__name__)


def wait_before_kill(process, wait=5, timeout=1):
    while wait > 0:
        logger.info(f'Time left before {process} will be killed: {wait*timeout}s')
        if not process.is_alive():
            break
        time.sleep(timeout)
        wait -= 1
    if process.is_alive():
        os.kill(process.pid, signal.SIGKILL)


class BFGBase(object):
    """
    A BFG load generator that manages multiple workers as processes and
    threads in each of them and feeds them with tasks
    """

    def __init__(self, gun, instances, stpd_filename, cached_stpd=False,
                 green_threads_per_instance=None, **kwargs):
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
        self.feeder = th.Thread(target=self._feed, name="Feeder", daemon=True)
        self.workers_finished = False
        self.start_time = None
        self.plan = None
        self.green_threads_per_instance = green_threads_per_instance

    def _worker(self):
        raise NotImplementedError

    def start(self):
        self.start_time = time.time()
        for process in self.pool:
            # process.daemon = True
            process.start()
        self.feeder.start()

    @property
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
        logger.info('killing processes')
        killers = [th.Thread(target=wait_before_kill, args=(p,)) for p in self.pool]
        for k in killers:
            k.start()
        for k in killers:
            k.join()
        try:
            while not self.task_queue.empty():
                logger.info('emptying queue')
                self.task_queue.get(timeout=0.1)
            logger.info('queue emptied')
            self.task_queue.close()
            logger.info('joining feeder')
            self.feeder.join()
            logger.info('feeder joined')
        except Exception as ex:
            logger.info(ex)

    def _feed(self):
        """
        A feeder that runs in distinct thread in main process.
        """
        try:
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
        except (KeyboardInterrupt, SystemExit):
            self.task_queue.close()
            self.results.close()
            self.quit.set()
            logger.info("Going to quit. Killing workers")
            [os.kill(x.pid, signal.SIGKILL) for x in self.pool if x.is_alive()]
            logger.info("All workers exited.")
            self.workers_finished = True
        else:
            logger.info("Waiting for workers")
            list(map(lambda x: x.join(), self.pool))
            logger.info("All workers exited.")
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
                    self.gun.shoot(missile, marker)
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
        logger.info("Exit shooter process")


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

        list(map(lambda g: g.join(), self.green_pool))

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

                    self.gun.shoot(missile, marker)
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


class BFGMeasureCounter(BFGBase):

    def start(self):
        super(BFGMeasureCounter, self).start()
        th.Thread(target=self._monitor_worker_business, name='WorkerBusinessMonitor', daemon=True).start()

    @property
    def max_instances(self):
        return self.gun.get_option('max_instances')

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
                with self.instance_counter.get_lock():
                    self.instance_counter.value += 1
                self.gun.shoot(None, None)
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
            finally:
                with self.instance_counter.get_lock():
                    self.instance_counter.value -= 1
        try:
            self.gun.teardown()
        except Exception:
            logger.exception("Couldn't finalize gun. Exit shooter process")
            return
        logger.debug("Exit shooter process")

    def _put_killer_task_into_queue(self):
        retry_delay = 1
        while True:
            try:
                self.gun.q.put(None, timeout=1)
                break
            except Full:
                logger.debug(
                    "Couldn't post killer task"
                    " because queue is full. Retrying in %ss", retry_delay)
                time.sleep(retry_delay)
                if retry_delay >= 30:
                    retry_delay = 30
                else:
                    retry_delay *= 2
            except AssertionError:
                logger.debug(
                    "Couldn't post killer task"
                    " because queue is closed:"
                )
                break

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
                    timestamp, _, _ = task
                    self.gun.q.put(timestamp, timeout=1)
                    break
                except Full:
                    if self.quit.is_set() or self.workers_finished:
                        return
                    else:
                        continue

        workers_count = len(self.pool)
        logger.info(
            "Fed all data. Publishing %d killer tasks" % (workers_count))

        for _ in range(0, workers_count):
            self._put_killer_task_into_queue()
        try:
            logger.info("Waiting for workers")
            list(map(lambda p: p.join(), self.pool))
            logger.info("All workers exited.")
            self.workers_finished = True
        except (KeyboardInterrupt, SystemExit):
            self.task_queue.close()
            self.results.close()
            if isinstance(self.gun, MeasureCounterGun):
                self.gun.please_stop.set()
            self.gun.q.close()
            self.quit.set()
            logger.info("Going to quit. Waiting for workers")
            list(map(lambda p: p.join(), self.pool))
            self.workers_finished = True

    def _monitor_worker_business(self, critical_overload_duration=3):
        """
        monitores gun of type MeasureCounterGun values and decides if test needs more workers
        after adding workers, it must wait for some time and check again after next_check_timeout
        must be called in a separate thread.
        addition criteria are as follows:
        once critical percentage of late measures is reached SOME (heuristic) amount of workers are being added
        next check compares previous percentage with current and adds new workers, only if newer late measures
        have been occurring for critical_overload_duration time
        :param critical_overload_duration: (heuristics) duration percentage of "late" measures,
            that triggers adding workers procedure
        :return:
        """
        late_percentage = 0
        overload_duration = 0
        while not self.workers_finished and not self.quit.is_set():
            time.sleep(1)
            if not isinstance(self.gun, MeasureCounterGun):
                logger.warning("Wrong gun type for worker business monitoring. Expected MeasureCounterGun")
                return
            late = self.gun.late_measures.value
            count = self.gun.measure_count.value
            new_late_percentage = 100*late/count if count else 0
            logger.debug(f'{round(new_late_percentage - late_percentage, 2)}% duration {overload_duration}s')
            if new_late_percentage - late_percentage > 0:
                overload = new_late_percentage - late_percentage
                overload_duration += 1
            else:
                overload = 0
                overload_duration = 0
                late_percentage = new_late_percentage
            if overload and overload_duration > critical_overload_duration:
                if len(self.pool) < self.max_instances:
                    quantity = int(len(self.pool) * overload // 100) + 1
                    self._add_pool_workers(quantity=quantity)
                    overload_duration = 0
                    late_percentage = new_late_percentage
                else:
                    logger.info(f'Maximum amount of instances reached {self.max_instances}')

    def _add_pool_workers(self, quantity=1):
        if not self.workers_finished and not self.quit.is_set():
            # FIXME: race condition possible?
            for _ in range(quantity):
                # FIXME: might insert a killer task in the middle of a queue, if not all task data is fed by the feeder
                self._put_killer_task_into_queue()
                p = mp.Process(target=self._worker)
                self.pool.append(p)
                p.start()
            logger.info(f"ADDED {quantity} WORKER{'S' if quantity > 1 else ''} current pool = {len(self.pool)}")
