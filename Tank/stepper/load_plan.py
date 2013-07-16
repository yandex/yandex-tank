'''
Load Plan generators
'''
import math
import re
from util import parse_duration
from itertools import chain, groupby
from info import STATUS


class Const(object):

    '''
    Load plan with constant load
    '''

    def __init__(self, rps, duration):
        self.rps = float(rps)
        self.duration = duration

    def __iter__(self):
        if self.rps == 0:
            return iter([])
        interval = 1000.0 / self.rps
        return (int(i * interval) for i in xrange(0, int(self.rps * self.duration / 1000)))

    def rps_at(self, t):
        '''Return rps for second t'''
        if t <= self.duration:
            return self.rps
        else:
            return 0

    def get_duration(self):
        '''Return step duration'''
        return self.duration

    def __len__(self):
        '''Return total ammo count'''
        return self.duration * self.rps

    def get_rps_list(self):
        return [(self.rps, self.duration / 1000)]


class Line(object):

    '''Load plan with linear load'''

    def __init__(self, minrps, maxrps, duration):
        # FIXME: does not work for negative k (minrps > maxrps)
        if minrps > maxrps:
            raise NotImplementedError(
                "We have no support for descending linear load yet")
        self.minrps = float(minrps)
        self.maxrps = float(maxrps)
        self.duration = duration / 1000.0
        self.k = (self.maxrps - self.minrps) / self.duration
        self.b = 1 + 2 * self.minrps / self.k

    def __iter__(self):
        k = self.k
        b = self.b

        '''
        Solve equation:
        n(t) = k/2 * t^2 + (k/2 + r0) * t
        where r(t) = k(t + 1/2) + r0 -- rps
        r0 is initial rps.
        '''
        def timestamp(n):
            return int((math.sqrt(b ** 2 + 8 * n / k) - b) / 2 * 1000)  # (sqrt(b^2 + 8 * n / k) - b) / 2 -- time in seconds

        ''' Find ammo count given the time '''
        def number(t):
            return int(k * (t ** 2) / 2 + (k / 2 + self.minrps) * self.duration)
        return (timestamp(n) for n in xrange(0, self.__len__()))

    def rps_at(self, t):
        '''Return rps for second t'''
        if t <= self.duration:
            return self.minrps + float(self.maxrps - self.minrps) * t / self.duration
        else:
            return 0

    def get_duration(self):
        '''Return step duration'''
        return int(self.duration * 1000)

    def __len__(self):
        '''Return total ammo count'''
        return int(self.k * (self.duration ** 2) / 2 + (self.k / 2 + self.minrps) * self.duration)

    def get_float_rps_list(self):
        '''
        get list of constant load parts (we have no constant load at all, but tank will think so),
        with parts durations (float)
        '''
        int_rps = xrange(int(self.minrps), int(self.maxrps) + 1)
        step_duration = float(self.duration * 1000) / len(int_rps)
        return [(rps, int(step_duration)) for rps in int_rps]

    def get_rps_list(self):
        '''
        get list of each second's rps
        '''
        seconds = xrange(0, int(self.duration))
        rps_groups = groupby([int(self.rps_at(t))
                              for t in seconds], lambda x: x)
        rps_list = [(rps, len(list(rpl))) for rps, rpl in rps_groups]
        return rps_list


class Composite(object):

    '''Load plan with multiple steps'''

    def __init__(self, steps):
        self.steps = steps

    def __iter__(self):
        base = 0
        for step in self.steps:
            for ts in step:
                yield ts + base
            base += step.get_duration()

    def get_duration(self):
        '''Return total duration'''
        return sum(step.get_duration() for step in self.steps)

    def __len__(self):
        '''Return total ammo count'''
        return sum(step.__len__() for step in self.steps)

    def get_rps_list(self):
        return list(chain.from_iterable(step.get_rps_list() for step in self.steps))


class Stairway(Composite):

    def __init__(self, minrps, maxrps, increment, duration):
        if maxrps < minrps:
            increment = -increment
        n_steps = (maxrps - minrps) / increment
        steps = [
            Const(minrps + i * increment, duration)
            for i in xrange(0, n_steps + 1)
        ]
        super(Stairway, self).__init__(steps)


class StepFactory(object):

    @staticmethod
    def line(params):
        template = re.compile('(\d+),\s*(\d+),\s*([0-9.]+[dhms]?)+\)')
        minrps, maxrps, duration = template.search(params).groups()
        return Line(int(minrps), int(maxrps), parse_duration(duration))

    @staticmethod
    def const(params):
        template = re.compile('(\d+),\s*([0-9.]+[dhms]?)+\)')
        rps, duration = template.search(params).groups()
        return Const(int(rps), parse_duration(duration))

    @staticmethod
    def stairway(params):
        template = re.compile('(\d+),\s*(\d+),\s*(\d+),\s*([0-9.]+[dhms]?)+\)')
        minrps, maxrps, increment, duration = template.search(params).groups()
        return Stairway(int(minrps), int(maxrps), int(increment), parse_duration(duration))

    @staticmethod
    def produce(step_config):
        _plans = {
            'line': StepFactory.line,
            'const': StepFactory.const,
            'step': StepFactory.stairway,
        }
        load_type, params = step_config.split('(')
        load_type = load_type.strip()
        if load_type in _plans:
            return _plans[load_type](params)
        else:
            raise NotImplementedError(
                'No such load type implemented: "%s"' % load_type)


def create(rps_schedule):
    '''
    Create Load Plan as defined in schedule. Publish info about its duration.

    >>> from util import take

    >>> take(100, create(['line(1, 5, 2s)']))
    [0, 414, 732, 1000, 1236, 1449, 1645, 1828]

    >>> take(100, create(['const(1, 10s)']))
    [0, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000]

    >>> take(100, create(['const(200, 0.1s)']))
    [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95]

    >>> take(100, create(['const(1, 2s)', 'const(2, 2s)']))
    [0, 1000, 2000, 2500, 3000, 3500]
    '''
    if len(rps_schedule) > 1:
        lp = Composite([StepFactory.produce(step_config)
                       for step_config in rps_schedule])
    else:
        lp = StepFactory.produce(rps_schedule[0])
    STATUS.publish('duration', lp.get_duration())
    return lp
