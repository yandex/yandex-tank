'''
Load Plan generators
'''
import re
from itertools import chain, groupby
from builtins import range
from . import info
from .util import parse_duration, solve_quadratic, proper_round


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
        return (
            int(i * interval)
            for i in range(0, int(self.rps * self.duration / 1000)))

    def rps_at(self, t):
        '''Return rps for second t'''
        if 0 <= t <= self.duration:
            return self.rps
        else:
            return 0

    def get_duration(self):
        '''Return step duration'''
        return self.duration

    def __len__(self):
        '''Return total ammo count'''
        return int(self.duration / 1000 * self.rps)

    def get_rps_list(self):
        return [(int(self.rps), self.duration / 1000)]

    def __repr__(self):
        return 'const(%s, %s)' % (self.rps, self.duration / 1000)


class Line(object):
    '''Load plan with linear load'''

    def __init__(self, minrps, maxrps, duration):
        """

        :param minrps:
        :param maxrps:
        :param duration: milliseconds
        """
        self.minrps = float(minrps)
        self.maxrps = float(maxrps)
        self.duration = duration / 1000.0
        self.slope = (self.maxrps - self.minrps) / self.duration

    def ts(self, n):
        """
        :param n: number of charge
        :return: when to shoot nth charge, milliseconds
        """
        try:
            root1, root2 = solve_quadratic(self.slope / 2.0, self.minrps, -n)
        except ZeroDivisionError:
            root2 = float(n) / self.minrps
        return int(root2 * 1000)

    def __iter__(self):
        """

        :return: timestamps for each charge
        """
        return (self.ts(n) for n in range(0, self.__len__()))

    def rps_at(self, t):
        '''Return rps for second t'''
        if 0 <= t <= self.duration:
            return self.minrps + \
                float(self.maxrps - self.minrps) * t / self.duration
        else:
            return 0

    def get_duration(self):
        '''Return load duration in seconds'''
        return int(self.duration * 1000)

    def __len__(self):
        '''Return total ammo count'''
        return int((self.maxrps + self.minrps) / 2.0 * self.duration)

    def get_float_rps_list(self):
        '''
        get list of constant load parts (we have no constant load at all, but tank will think so),
        with parts durations (float)
        '''
        int_rps = range(int(self.minrps), int(self.maxrps) + 1)
        step_duration = float(self.duration) / len(int_rps)
        rps_list = [(rps, int(step_duration)) for rps in int_rps]
        return rps_list

    def get_rps_list(self):
        """
        get list of each second's rps
        :returns: list of tuples (rps, duration of corresponding rps in seconds)
        :rtype: list
        """
        seconds = range(0, int(self.duration) + 1)
        rps_groups = groupby([proper_round(self.rps_at(t)) for t in seconds],
                             lambda x: x)
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
        return int(sum(step.__len__() for step in self.steps))

    def get_rps_list(self):
        return list(
            chain.from_iterable(step.get_rps_list() for step in self.steps))


class Stairway(Composite):
    def __init__(self, minrps, maxrps, increment, step_duration):
        if maxrps < minrps:
            increment = -increment
        n_steps = int((maxrps - minrps) / increment)
        steps = [
            Const(minrps + i * increment, step_duration)
            for i in range(0, n_steps + 1)
        ]
        if increment > 0:
            if (minrps + n_steps * increment) < maxrps:
                steps.append(Const(maxrps, step_duration))
        elif increment < 0:
            if (minrps + n_steps * increment) > maxrps:
                steps.append(Const(maxrps, step_duration))
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
        template = re.compile(
            '([0-9.]+),\s*([0-9.]+),\s*([0-9.]+),\s*([0-9.]+[dhms]?)+\)')
        minrps, maxrps, increment, duration = template.search(params).groups()
        return Stairway(
            float(minrps),
            float(maxrps), float(increment), parse_duration(duration))

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
    """
    Create Load Plan as defined in schedule. Publish info about its duration.
    """
    if len(rps_schedule) > 1:
        lp = Composite(
            [StepFactory.produce(step_config) for step_config in rps_schedule])
    else:
        lp = StepFactory.produce(rps_schedule[0])
    info.status.publish('duration', lp.get_duration() / 1000)
    info.status.publish('steps', lp.get_rps_list())
    info.status.lp_len = len(lp)
    return lp
