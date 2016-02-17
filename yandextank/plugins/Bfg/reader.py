import pandas as pd
import time


def records_to_df(records):
    records = pd.DataFrame.from_records(records)
    records['receive_ts'] = records['send_ts'] + records['interval_real'] / 1e6
    records['receive_sec'] = records.receive_ts.astype(int)
    # TODO: consider configuration for the following:
    records['tag'] = records.tag.str.rsplit('#', 1, expand=True)[0]
    records.set_index(['receive_sec'], inplace=True)
    return records


class BfgReader(object):
    def __init__(self, results):
        self.buffer = ""
        self.stat_buffer = ""
        self.results = results
        self.closed = False
        # self.stat_queue = q.Queue()
        # self.stats_reader = JMeterStatAggregator(TimeChopper(
        #     self.__read_stat_queue(), 3))

        # def __read_stat_queue(self):
        #     while not self.closed:
        #         for _ in range(self.stat_queue.qsize()):
        #             try:
        #                 si = self.stat_queue.get_nowait()
        #                 if si is not None:
        #                     yield si
        #             except q.Empty:
        #                 break

    def next(self):
        if self.closed:
            raise StopIteration
        records = []
        while not self.results.empty():
            records.append(self.results.get(1))
        if records:
            df = records_to_df(records)
            #self.stat_queue.put(df)
            return df
        return None

    def __iter__(self):
        return self

    def close(self):
        self.closed = True


class BfgStatsReader(object):
    def __init__(self):
        self.closed = False

    def __iter__(self):
        while not self.closed:
            yield [{'ts': int(time.time()),
                    'metrics': {'instances': 0,
                                'reqps': 0}}]

    def close(self):
        self.closed = True
