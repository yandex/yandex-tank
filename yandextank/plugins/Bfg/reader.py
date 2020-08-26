import pandas as pd
import time
import itertools as itt
from queue import Empty
from threading import Lock
import threading as th
import logging
logger = logging.getLogger(__name__)


def records_to_df(records):
    records = pd.DataFrame.from_records(records)
    records['receive_ts'] = records['send_ts'] + records['interval_real'] / 1e6
    records['receive_sec'] = records.receive_ts.astype(int)
    # TODO: consider configuration for the following:
    records['tag'] = records.tag.str.rsplit('#', 1, expand=True)[0]
    records.set_index(['receive_sec'], inplace=True)
    return records


def _expand_steps(steps):
    return list(itt.chain(
        * [[rps] * int(duration) for rps, duration in steps]))


class BfgReader(object):
    def __init__(self, results, closed):
        self.buffer = ""
        self.stat_buffer = ""
        self.results = results
        self.closed = closed
        self.records = []
        self.lock = Lock()
        self.thread = th.Thread(target=self._cacher)
        self.thread.start()

    def _cacher(self):
        while True:
            try:
                self.records.append(
                    self.results.get(block=False))
            except Empty:
                if not self.closed.is_set():
                    time.sleep(0.1)
                else:
                    break

    def __next__(self):
        if self.closed.is_set():
            self.thread.join()
            raise StopIteration
        with self.lock:
            records = self.records
            self.records = []
        if records:
            return records_to_df(records)
        return None

    def __iter__(self):
        return self


class BfgStatsReader(object):
    def __init__(self, instance_counter, steps):
        self.closed = False
        self.last_ts = 0
        self.steps = _expand_steps(steps)
        self.instance_counter = instance_counter
        self.start_time = int(time.time())

    def __iter__(self):
        while not self.closed:
            cur_ts = int(time.time())
            if cur_ts > self.last_ts:
                offset = cur_ts - self.start_time
                reqps = 0
                if offset >= 0 and offset < len(self.steps):
                    reqps = self.steps[offset]
                yield [{
                    'ts': cur_ts,
                    'metrics': {
                        'instances': self.instance_counter.value,
                        'reqps': reqps
                    }
                }]
                self.last_ts = cur_ts
            else:
                yield []

    def close(self):
        self.closed = True
