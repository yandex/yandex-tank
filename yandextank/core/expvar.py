"""
Global metrics publishing module. Inspired by Golang's expvar module

This implementation is not thread-safe
"""

from queue import Queue, Empty
import time


class ExpVar(object):
    """
    This class stores variables
    """

    def __init__(self):
        self.variables = {}

    def publish(self, name, var):
        if name in self.variables:
            raise RuntimeError(
                "'%s' variable have been already published before" % name)
        self.variables[name] = var
        return var

    def get(self, name):
        if name not in self.variables:
            raise RuntimeError("No such variable: %s", name)
        return self.variables[name]

    def get_dict(self):
        return {k: v.get() for k, v in self.variables.iteritems()}


class Var(object):
    """
    This class stores generic variable value.
    It is also a base class for other variable types
    """

    def __init__(self, value=None):
        self.value = value

    def set(self, value):
        self.value = value

    def get(self):
        return self.value

    def __str__(self):
        return str(self.value)


class Int(Var):
    def __init__(self, value=0):
        if not isinstance(value, int):
            raise ValueError(
                "Value should be an integer, but it is '%s'" % type(value))
        super(Int, self).__init__(value)

    def inc(self, delta=1):
        self.value += delta


class Metric(object):
    """
    This class stores generic time-series data in a queue.
    Values are stored as (timestamp, value) tuples
    """

    def __init__(self):
        self.metric = Queue()

    def push(self, value, timestamp=None):
        if timestamp is None:
            timestamp = int(time.time())
        elif not isinstance(timestamp, int):
            raise ValueError(
                "Timestamp should be an integer, but it is '%s'" %
                type(timestamp))
        self.metric.put((timestamp, value))

    def next(self):
        try:
            return self.metric.get_nowait()
        except Empty:
            raise StopIteration

    def get(self):
        # TODO: decide what we should return here
        return None

    def __iter__(self):
        return self


EV = ExpVar()


def publish(name, var):
    return EV.publish(name, var)


def get(name):
    return EV.get(name)


def get_dict():
    return EV.get_dict()
