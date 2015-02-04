from yandextank.plugins.Aggregator import AbstractReader
from yandextank.stepper import info as si


class BFGReader(AbstractReader):

    '''
    Listens results from BFG and provides them to Aggregator
    '''

    def __init__(self, aggregator, bfg, result_cache_size=5):
        AbstractReader.__init__(self, aggregator)
        self.bfg = bfg
        self.result_cache_size = result_cache_size
        self.steps = map(list, si.status.get_info().steps)

    def get_next_sample(self, force):
        new_data = []
        while not self.bfg.results.empty():
            new_data.append(self.bfg.results.get(1))
        for cur_time, sample in new_data:
            if not cur_time in self.data_buffer.keys():
                self.data_queue.append(cur_time)
                self.data_buffer[cur_time] = []
            self.data_buffer[cur_time].append(list(sample))
        if self.data_queue and len(self.data_queue) >= self.result_cache_size:
            res = self.pop_second()
            res.overall.planned_requests = self.__get_expected_rps()
            return res
        else:
            return None

    def __get_expected_rps(self):
        '''
        Mark second with expected rps
        '''
        while self.steps and self.steps[0][1] < 1:
            self.steps.pop(0)
        
        if not self.steps:
            return 0
        else:
            self.steps[0][1] -= 1
            return self.steps[0][0]