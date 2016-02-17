#TODO


class BfgReader(object):
    def __init__(self, filename):
        self.buffer = ""
        self.stat_buffer = ""
        self.jtl = open(filename, 'r')
        self.closed = False
        self.stat_queue = q.Queue()
        self.stats_reader = JMeterStatAggregator(TimeChopper(
            self.__read_stat_queue(), 3))

    def __read_stat_queue(self):
        while not self.closed:
            for _ in range(self.stat_queue.qsize()):
                try:
                    si = self.stat_queue.get_nowait()
                    if si is not None:
                        yield si
                except q.Empty:
                    break

    def next(self):
        if self.closed:
            raise StopIteration
        data = self.jtl.read(1024 * 1024 * 10)
        if data:
            parts = data.rsplit('\n', 1)
            if len(parts) > 1:
                ready_chunk = self.buffer + parts[0] + '\n'
                self.buffer = parts[1]
                df = string_to_df(ready_chunk)
                self.stat_queue.put(df)
                return df
            else:
                self.buffer += parts[0]
        else:
            self.jtl.readline()
        return None

    def __iter__(self):
        return self

    def close(self):
        self.closed = True
        self.jtl.close()
