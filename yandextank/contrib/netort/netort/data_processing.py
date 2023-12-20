import logging
try:
    import queue as q
except ImportError:
    import Queue as q
import threading
import time


logger = logging.getLogger(__name__)


def get_nowait_from_queue(queue):
    """ Collect all immediately available items from a queue """
    data = []
    for _ in range(queue.qsize()):
        try:
            data.append(queue.get_nowait())
        except q.Empty:
            break
    return data


class Drain(threading.Thread):
    """
    Drain a generator to a destination that answers to put(), in a thread
    """

    def __init__(self, source, destination):
        super(Drain, self).__init__()
        self.source = source
        self.destination = destination
        self._finished = threading.Event()
        self._interrupted = threading.Event()
        self.daemon = True  # bdk+ytank stuck w/o this at join of this thread

    def run(self):
        try:
            for item in self.source:
                self.destination.put(item)
                if self._interrupted.is_set():
                    break
        except Exception as e:
            logger.error(e, exc_info=True)
            self._interrupted.set()
        finally:
            self._finished.set()

    def wait(self, timeout=None):
        self._finished.wait(timeout=timeout)

    def close(self):
        self._interrupted.set()


class Tee(threading.Thread):
    """Copy items from one queue to multiple in a thread.

    Note:
        Items are passed by reference.
    """

    def __init__(self, source, destination, type):
        """
        Args:
            source (queue): where to get items from
            destination (list): list of queues where to put items from the source
            type (string): ???
        """
        # TODO: what is type?!
        super(Tee, self).__init__()
        self.source = source
        self.destination = destination  # TODO: this is actually a list of destinations. Rename.
        self.type = type
        self._finished = threading.Event()
        self._interrupted = threading.Event()
        self.daemon = True  # just in case, bdk+ytank stuck w/o this at join of Drain thread

    def run(self):
        while not self._interrupted.is_set():
            data = get_nowait_from_queue(self.source)
            for item in data:
                for destination in self.destination:
                    destination.put(item, self.type)
                    if self._interrupted.is_set():
                        break
                if self._interrupted.is_set():
                    break
            if self._interrupted.is_set():
                break
            time.sleep(0.5)
        self._finished.set()

    def wait(self, timeout=None):
        self._finished.wait(timeout=timeout)

    def close(self):
        self._interrupted.set()


# TODO: does it really chop anything?
class Chopper(object):
    def __init__(self, source):
        self.source = source

    def __iter__(self):
        for chunk in self.source:
            for item in chunk:
                yield item
