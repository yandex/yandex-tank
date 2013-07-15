from itertools import cycle, chain
from util import parse_duration
import re


class InstanceLP(object):

    '''Base class for all instance plans'''

    def __init__(self, duration=0):
        self.duration = float(duration)

    def get_duration(self):
        '''Return step duration'''
        return self.duration

    def __len__(self):
        '''Return total ammo count'''
        return 0

    def get_rps_list(self):
        return []


class Empty(InstanceLP):

    '''Load plan with no timestamp (for instance_schedule)'''

    def __iter__(self):
        return cycle([0])


class Composite(InstanceLP):

    '''Load plan with multiple steps'''

    def __init__(self, steps):
        self.steps = steps

    def __iter__(self):
        base = 0
        for step in self.steps:
            for ts in step:
                yield int(ts + base)
            base += step.get_duration() * 1000
        for item in cycle([0]):
            yield item

    def get_duration(self):
        '''Return total duration'''
        return sum(step.get_duration() for step in self.steps)

    def __len__(self):
        '''Return total ammo count'''
        return sum(step.__len__() for step in self.steps)

    def get_rps_list(self):
        return list(chain.from_iterable(step.get_rps_list() for step in self.steps))


class Line(InstanceLP):

    '''
    Starts some instances linearly

    >>> list(Line(5, 5))
    [0, 1000, 2000, 3000, 4000]
    '''

    def __init__(self, instances, duration):
        self.instances = instances
        self.duration = float(duration)

    def __iter__(self):
        instances_per_second = self.instances / self.duration
        interval = 1000 / instances_per_second
        return (int(i * interval) for i in xrange(0, self.instances))


class Ramp(InstanceLP):

    '''
    Starts <instance_count> instances, one each <interval> seconds

    >>> list(Ramp(5, 5))
    [0, 5000, 10000, 15000, 20000]
    '''

    def __init__(self, instance_count, interval):
        self.duration = float(instance_count * interval)
        self.instance_count = instance_count
        self.interval = float(interval) * 1000

    def __iter__(self):
        return ((int(i * self.interval) for i in xrange(0, self.instance_count)))


class Wait(InstanceLP):

    '''
    Don't start any instances for the definded duration
    '''

    def __init__(self, duration):
        self.duration = float(duration)

    def __iter__(self):
        return iter([])


class Stairway(InstanceLP):

    def __init__(self, minrps, maxrps, increment, duration):
        raise NotImplementedError(
            'We have no support for this load type in instances_schedule yet')


class StepFactory(object):

    @staticmethod
    def line(params):
        template = re.compile('(\d+),\s*(\d+),\s*(\d+[dhms]?)+\)')
        minrps, maxrps, duration = template.search(params).groups()
        # note that we don't use minrps at all and use maxrps
        # as the number of instances we gonna start
        return Line(int(maxrps - minrps), parse_duration(duration))

    @staticmethod
    def ramp(params):
        template = re.compile('(\d+),\s*(\d+[dhms]?)+\)')
        instances, interval = template.search(params).groups()
        return Ramp(int(instances), parse_duration(interval))

    @staticmethod
    def wait(params):
        template = re.compile('(\d+[dhms]?)+\)')
        duration = template.search(params).groups()[0]
        return Wait(parse_duration(duration))

    @staticmethod
    def stairway(params):
        template = re.compile('(\d+),\s*(\d+),\s*(\d+),\s*(\d+[dhms]?)+\)')
        minrps, maxrps, increment, duration = template.search(params).groups()
        return Stairway(int(minrps), int(maxrps), int(increment), parse_duration(duration))

    @staticmethod
    def produce(step_config):
        _plans = {
            'line': StepFactory.line,
            'step': StepFactory.stairway,
            'ramp': StepFactory.ramp,
            'wait': StepFactory.wait,
        }
        load_type, params = step_config.split('(')
        load_type = load_type.strip()
        if load_type in _plans:
            return _plans[load_type](params)
        else:
            raise NotImplementedError(
                'No such load type implemented for instances_schedule: "%s"' % load_type)


def create(instances_schedule):
    '''
    Creates load plan timestamps generator

    >>> from itertools import islice
    >>> from util import take

    >>> lp = create(['ramp(5, 5s)'])
    >>> take(7, lp)
    [0, 5000, 10000, 15000, 20000, 0, 0]

    >>> lp = create(['ramp(5, 5s)', 'wait(5s)', 'ramp(5,5s)'])
    >>> take(12, lp)
    [0, 5000, 10000, 15000, 20000, 30000, 35000, 40000, 45000, 50000, 0, 0]

    >>> lp = create(['wait(5s)', 'ramp(5, 0)'])
    >>> take(7, lp)
    [5000, 5000, 5000, 5000, 5000, 0, 0]
    '''
    if len(instances_schedule) > 1:
        steps = [StepFactory.produce(step_config)
                 for step_config in instances_schedule]
    else:
        steps = [StepFactory.produce(instances_schedule[0])]
    return Composite(steps)
