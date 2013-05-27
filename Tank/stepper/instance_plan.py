from itertools import cycle
#from util import parse_duration


class Empty(object):
    '''Load plan with no timestamp (for instance_schedule)'''
    def __init__(self, duration=0):
        self.duration = duration

    def __iter__(self):
        return cycle([None])

    def get_duration(self):
        '''Return step duration'''
        return self.duration

    def __len__(self):
        '''Return total ammo count'''
        return 0
