"""
Split incoming DataFrames into chunks, cache them, union chunks with same key
and pass to the underlying aggregator.
"""


class Chopper(object):
    def __init__(self, arg):
        self.arg = arg
