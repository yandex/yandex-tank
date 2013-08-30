from itertools import cycle
from util import parse_duration
from module_exceptions import StepperConfigurationError
import re
import info
import logging


class InstanceLP(object):

    '''Base class for all instance plans'''

    def __init__(self, duration=0):
        self.duration = float(duration)

    def get_duration(self):
        return int(self.duration)  # needed for Composite LP


class Composite(InstanceLP):

    '''Load plan with multiple steps'''

    def __init__(self, steps):
        self.steps = steps

    def __iter__(self):
        base = 0
        for step in self.steps:
            for ts in step:
                yield int(ts + base)
            base += step.get_duration()
        for item in cycle([0]):
            yield item

    def __len__(self):
        return sum(len(step) for step in self.steps)


class Ramp(InstanceLP):

    '''
    Starts some instances in a specified interval

    >>> from util import take
    >>> take(10, Ramp(5, 5000))
    [0, 1000, 2000, 3000, 4000]
    '''

    def __init__(self, instances, duration):
        self.instances = instances
        self.duration = float(duration)

    def __iter__(self):
        interval = float(self.duration) / self.instances
        return (int(i * interval) for i in xrange(0, self.instances))

    def __len__(self):
        return self.instances


class Wait(InstanceLP):

    '''
    Don't start any instances for the definded duration
    '''

    def __init__(self, duration):
        self.duration = duration

    def __iter__(self):
        return iter([])

    def __len__(self):
        return 0


class Stairway(InstanceLP):

    def __init__(self, minrps, maxrps, increment, duration):
        raise NotImplementedError(
            'We have no support for this load type in instances_schedule yet')


class StepFactory(object):

    @staticmethod
    def ramp(params):
        template = re.compile('(\d+),\s*([0-9.]+[dhms]?)+\)')
        s_res = template.search(params)
        if s_res:
            instances, interval = s_res.groups()
            return Ramp(int(instances), parse_duration(interval))
        else:
            logging.info(
                "Ramp step format: 'ramp(<instances_to_start>, <step_duration>)'")
            raise StepperConfigurationError(
                "Error in step configuration: 'ramp(%s'" % params)

    @staticmethod
    def wait(params):
        template = re.compile('([0-9.]+[dhms]?)+\)')
        s_res = template.search(params)
        if s_res:
            duration = s_res.groups()[0]
            return Wait(parse_duration(duration))
        else:
            logging.info("Wait step format: 'wait(<step_duration>)'")
            raise StepperConfigurationError(
                "Error in step configuration: 'wait(%s'" % params)

    @staticmethod
    def stairway(params):
        template = re.compile('(\d+),\s*(\d+),\s*(\d+),\s*([0-9.]+[dhms]?)+\)')
        minrps, maxrps, increment, duration = template.search(params).groups()
        return Stairway(int(minrps), int(maxrps), int(increment), parse_duration(duration))

    @staticmethod
    def produce(step_config):
        _plans = {
            #  'line': StepFactory.line,
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

    >>> from util import take

    >>> take(7, create(['ramp(5, 5s)']))
    [0, 1000, 2000, 3000, 4000, 0, 0]

    >>> take(12, create(['ramp(5, 5s)', 'wait(5s)', 'ramp(5,5s)']))
    [0, 1000, 2000, 3000, 4000, 10000, 11000, 12000, 13000, 14000, 0, 0]

    >>> take(7, create(['wait(5s)', 'ramp(5, 0)']))
    [5000, 5000, 5000, 5000, 5000, 0, 0]

    >>> take(7, create([]))
    [0, 0, 0, 0, 0, 0, 0]
    '''
    steps = [StepFactory.produce(step_config)
             for step_config in instances_schedule]
    lp = Composite(steps)
    info.status.publish('duration', 0)
    info.status.publish('steps', [])
    info.status.publish('instances', len(lp))
    return lp
