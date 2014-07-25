'''
Load Plan generators
'''
import re
from util import parse_duration, solve_quadratic
from itertools import chain, groupby
import info
import logging


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
        return self.duration / 1000 * self.rps

    def get_rps_list(self):
        return [(int(self.rps), self.duration / 1000)]

    def __repr__(self):
        return 'const(%s, %s)' % (self.rps, self.duration / 1000)


class Line(object):

    '''Load plan with linear load'''

    def __init__(self, minrps, maxrps, duration):
        self.minrps = float(minrps)
        self.maxrps = float(maxrps)
        self.duration = duration / 1000.0
        self.b = self.minrps
        self.k = (self.maxrps - self.minrps) / self.duration

    def ts(self, n):
            root1, root2 = solve_quadratic(self.k / 2.0, self.b, -n)
            return int(root2 * 1000)

    def __iter__(self):
        return (self.ts(n) for n in xrange(0, self.__len__()))

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
        return int(self.k / 2.0 * (self.duration ** 2) + self.b * self.duration)

    def get_float_rps_list(self):
        '''
        get list of constant load parts (we have no constant load at all, but tank will think so),
        with parts durations (float)
        '''
        int_rps = xrange(int(self.minrps), int(self.maxrps) + 1)
        step_duration = float(self.duration) / len(int_rps)
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
        n_steps = int((maxrps - minrps) / increment)
        steps = [
            Const(minrps + i * increment, duration)
            for i in xrange(0, n_steps + 1)
        ]
        if (n_steps + 1) * increment < maxrps:
            steps.append(Const(maxrps, duration))
        logging.info(steps)
        super(Stairway, self).__init__(steps)


class StepFactory(object):

    @staticmethod
    def line(params):
        template = re.compile('([0-9.]+),\s*([0-9.]+),\s*([0-9.]+[dhms]?)+\)')
        minrps, maxrps, duration = template.search(params).groups()
        return Line(float(minrps), float(maxrps), parse_duration(duration))

    @staticmethod
    def const(params):
        template = re.compile('([0-9.]+),\s*([0-9.]+[dhms]?)+\)')
        rps, duration = template.search(params).groups()
        return Const(float(rps), parse_duration(duration))

    @staticmethod
    def stairway(params):
        template = re.compile('([0-9.]+),\s*([0-9.]+),\s*([0-9.]+),\s*([0-9.]+[dhms]?)+\)')
        minrps, maxrps, increment, duration = template.search(params).groups()
        return Stairway(float(minrps), float(maxrps), float(increment), parse_duration(duration))

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
    [0, 618, 1000, 1302, 1561, 1791]

    >>> take(100, create(['line(1.1, 5.8, 2s)']))
    [0, 566, 917, 1196, 1435, 1647]

    >>> take(100, create(['line(5, 1, 2s)']))
    [0, 208, 438, 697, 1000, 1381]

    >>> take(100, create(['const(1, 10s)']))
    [0, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000]

    >>> take(100, create(['const(200, 0.1s)']))
    [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95]

    >>> take(100, create(['const(1, 2s)', 'const(2, 2s)']))
    [0, 1000, 2000, 2500, 3000, 3500]

    >>> take(100, create(['const(1.5, 10s)']))
    [0, 666, 1333, 2000, 2666, 3333, 4000, 4666, 5333, 6000, 6666, 7333, 8000, 8666, 9333]

    >>> take(10, create(['step(1, 5, 1, 5s)']))
    [0, 1000, 2000, 3000, 4000, 5000, 5500, 6000, 6500, 7000]

    >>> take(10, create(['step(1.2, 5.7, 1.1, 5s)']))
    [0, 833, 1666, 2500, 3333, 4166, 5000, 5434, 5869, 6304]

    >>> take(10, create(['const(1, 1)']))
    [0]

    '''
    if len(rps_schedule) > 1:
        lp = Composite([StepFactory.produce(step_config)
                       for step_config in rps_schedule])
    else:
        lp = StepFactory.produce(rps_schedule[0])
    info.status.publish('duration', lp.get_duration() / 1000)
    info.status.publish('steps', lp.get_rps_list())
    info.status.lp_len = len(lp)
    return lp
