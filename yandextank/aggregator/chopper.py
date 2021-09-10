"""
Split incoming DataFrames into chunks, cache them, union chunks with same key
and pass to the underlying aggregator.
"""

import pandas as pd


class TimeChopper(object):
    """
    TimeChopper splits incoming dataframes by index. Chunks are cached and
    chunks for same key from different DFs are joined. Then chunks are passed
    further as (<timestamp>, <dataframe>) tuples.
    """

    def __init__(self, sources):
        # self.cache_size = cache_size
        self.sources = sources
        self.cache = {}
        self.recent_ts = [0] * len(self.sources)

    def __iter__(self):
        try:
            while True:
                for n, source in enumerate(self.sources):
                    chunk = next(source)
                    if chunk is not None:
                        self.recent_ts[n] = chunk.index[-1]
                        grouped = chunk.groupby(level=0)
                        for ts, group_data in list(grouped):
                            if ts in self.cache:
                                self.cache[ts] = pd.concat(
                                    [self.cache[ts], group_data])
                            else:
                                self.cache[ts] = group_data
                last_ready_ts = min(self.recent_ts) - 1
                for ts in sorted(filter(lambda x: x <= last_ready_ts, self.cache)):
                    data = self.cache.pop(ts)
                    yield ts, data, len(data)
        except StopIteration:
            while self.cache:
                yield self.__get_result()

    def __get_result(self):
        ts = min(self.cache.keys())
        result = self.cache.pop(ts, None)
        cardinality = len(result) if result is not None else 0
        return ts, result, cardinality
