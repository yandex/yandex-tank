"""
Split incoming DataFrames into chunks, cache them, union chunks with same key
and pass to the underlying aggregator.
"""

import pandas as pd


class TimeChopper(object):
    """
    TimeChopper splits incoming dataframes by seconds (they must
    be indexed by a timestamp). Secondly chunks are cached and
    chunks for same second from different DF are joined. Then secondly
    chunks are passed further.
    """
    def __init__(self, source, cache_size):
        self.cache_size = cache_size
        self.source = source
        self.cache = {}

    def __iter__(self):
        for chunk in self.source:
            grouped = chunk.groupby(level=0)
            for group_key, group_data in list(grouped):
                if group_key in self.cache:
                    self.cache[group_key] = pd.concat([
                        self.cache[group_key], group_data])
                else:
                    self.cache[group_key] = group_data
                while len(self.cache) > self.cache_size:
                    key = min(self.cache.keys())
                    yield (key, self.cache.pop(key, None))
        while self.cache:
            key = min(self.cache.keys())
            yield (key, self.cache.pop(key, None))
