'''
Common utilities
'''
import threading as th
import logging


LOG = logging.getLogger(__name__)


class Drain(th.Thread):
    """
    Drain a generator to a destination that answers to put(), in a thread
    """
    def __init__(self, source, destination):
        super(Drain, self).__init__()
        self.source = source
        self.destination = destination
        self.stop = th.Event()

    def run(self):
        for item in self.source:
            self.destination.put(item)
            if self.stop.is_set():
                return

    def close(self):
        self.stop.set()
