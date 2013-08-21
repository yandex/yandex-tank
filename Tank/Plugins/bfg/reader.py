from Tank.Plugins.Aggregator import AbstractReader


class BFGReader(AbstractReader):

    '''
    Listens results from BFG and provides them to Aggregator
    '''

    def __init__(self, aggregator, bfg):
        AbstractReader.__init__(self, aggregator)
        self.bfg = bfg

    def get_next_sample(self, force):
        new_data = []
        while not self.bfg.results.empty():
            new_data.append(self.bfg.results.get())
        for cur_time, sample in new_data:
            if not cur_time in self.data_buffer.keys():
                self.data_queue.append(cur_time)
                self.data_buffer[cur_time] = []
            self.data_buffer[cur_time].append(list(sample))
        if self.data_queue:
            return self.pop_second()
        else:
            return None
