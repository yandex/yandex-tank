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

    def next(self):
        if self.closed:
            raise StopIteration
        records = []
        while not self.results.empty():
            records.append(self.results.get(1))
        if records:
            return records_to_df(records)
        return None

    def __iter__(self):
        return self

    def close(self):
        self.closed = True


class BfgStatsReader(object):
    def __init__(self, instance_counter):
        self.closed = False
        self.last_ts = 0
        self.instance_counter = instance_counter

    def __iter__(self):
        while not self.closed:
            cur_ts = int(time.time())
            if cur_ts > self.last_ts:
                yield [{'ts': cur_ts,
                        'metrics': {'instances': self.instance_counter.get(),
                                    'reqps': 0}}]
                self.last_ts = cur_ts
            else:
                yield []

    def close(self):
        self.closed = True
