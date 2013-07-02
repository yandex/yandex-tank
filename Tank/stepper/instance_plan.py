from itertools import cycle
from load_plan import Composite
from util import parse_duration
import re


class Empty(object):

    '''Load plan with no timestamp (for instance_schedule)'''

    def __init__(self, duration=0):
        self.duration = duration

    def __iter__(self):
        return cycle([0])

    def get_duration(self):
        '''Return step duration'''
        return self.duration

    def __len__(self):
        '''Return total ammo count'''
        return 0


class Line:

    '''
    Starts some instances linearly
    '''

    def __init__(self, instances, duration):
        self.instances = instances
        self.duration = float(duration)

    def __iter__(self):
        instances_per_second = self.instances / self.duration
        interval = 1000 / instances_per_second
        return (int(i * interval) for i in xrange(0, self.instances))

    def get_duration(self):
        '''Return total duration'''
        return 0

    def __len__(self):
        '''Return total ammo count'''
        return 0

    def get_rps_list(self):
        return []


class Stairway:

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
        return Line(int(maxrps), parse_duration(duration))

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
        }
        load_type, params = step_config.split('(')
        load_type = load_type.strip()
        if load_type in _plans:
            return _plans[load_type](params)
        else:
            raise NotImplementedError(
                'No such load type implemented for instances_schedule: "%s"' % load_type)


def create(instances_schedule):
    if len(instances_schedule) > 1:
        steps = [StepFactory.produce(step_config)
                 for step_config in instances_schedule]
    else:
        steps = [StepFactory.produce(instances_schedule[0])]
    return Composite(steps.append(Empty()))
