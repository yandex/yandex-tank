'''
Load Plan generators
'''
import math
import re
from util import parse_duration
from itertools import chain


class Const(object):
    '''Load plan with constant load'''
    def __init__(self, rps, duration):
        self.rps = rps
        self.duration = duration

    def __iter__(self):
        if self.rps == 0:
            return iter([])
        interval = 1000000 / self.rps
        return (i * interval for i in xrange(0, self.rps * self.duration))

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
        return [(self.duration, self.rps)]


class Line(object):
    '''Load plan with linear load'''
    def __init__(self, minrps, maxrps, duration):
        self.minrps = float(minrps)
        self.maxrps = float(maxrps)
        self.duration = float(duration)
        self.k = self.maxrps - self.minrps / self.duration
        print minrps, maxrps, duration
        self.b = 1 + 2 * self.minrps / self.k

    def __iter__(self):
        k = self.k
        b = self.b

        #FIXME: does not work for negative k (minrps > maxrps)
        if k < 0:
            raise NotImplementedError("We have no support for descending linear load yet")

        '''
        Solve equation:
        n(t) = k/2 * t^2 + (k/2 + r0) * t
        where r(t) = k(t + 1/2) + r0 -- rps
        r0 is initial rps.
        '''
        def timestamp(n):
            return int((math.sqrt(b ** 2 + 8 * n / k) - b) * 500000)  # (sqrt(b^2 + 8 * n / k) - b) / 2 -- time in seconds

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
        return self.duration

    def __len__(self):
        '''Return total ammo count'''
        return int(self.k * (self.duration ** 2) / 2 + (self.k / 2 + self.minrps) * self.duration)

    def get_rps_list(self):
        int_rps = xrange(int(self.minrps), int(self.maxrps) + 1)
        step_size = float(self.duration) / len(int_rps)
        print int_rps, self.k, self.b
        return [(step_size, rps) for rps in int_rps]


class Composite(object):
    '''Load plan with multiple steps'''
    def __init__(self, steps):
        self.steps = steps

    def __iter__(self):
        base = 0
        for step in self.steps:
            for ts in step:
                yield ts + base
            base += step.get_duration() * 1000000

    def get_duration(self):
        '''Return total duration'''
        return sum(step.get_duration() for step in self.steps)

    def __len__(self):
        '''Return total ammo count'''
        return sum(step.__len__() for step in self.steps)

    def get_rps_list(self):
        return list(chain(step.get_rps_list() for step in self.steps))


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
        template = re.compile('(\d+),\s*(\d+),\s*(\d+[dhms]?)+\)')
        minrps, maxrps, duration = template.search(params).groups()
        return Line(int(minrps), int(maxrps), parse_duration(duration))

    @staticmethod
    def const(params):
        template = re.compile('(\d+),\s*(\d+[dhms]?)+\)')
        rps, duration = template.search(params).groups()
        return Const(int(rps), parse_duration(duration))

    @staticmethod
    def stairway(params):
        template = re.compile('(\d+),\s*(\d+),\s*(\d+),\s*(\d+[dhms]?)+\)')
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
        if load_type in _plans:
            return _plans[load_type](params)
        else:
            raise NotImplemented('No such load type implemented: %s', load_type)


def create(rps_schedule):
    '''Load Plan factory method'''
    if len(rps_schedule) > 1:
        return Composite([StepFactory.produce(step_config) for step_config in rps_schedule])
    else:
        return StepFactory.produce(rps_schedule[0])
