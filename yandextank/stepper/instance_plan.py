import logging
import re
from . import info
from itertools import cycle, repeat, chain

from .util import parse_duration
from .module_exceptions import StepperConfigurationError
from builtins import range


class LoadPlanBuilder(object):
    def __init__(self):
        self.generators = []
        self.steps = []
        self.instances = 0
        self.duration = 0
        self.log = logging.getLogger(__name__)

    def start(self, count):
        self.log.debug("Start %s instances at %sms" % (count, self.duration))
        if count < 0:
            raise StepperConfigurationError(
                "Can not stop instances in instances_schedule.")
        self.generators.append(repeat(int(self.duration), count))
        self.instances += count
        return self

    def wait(self, duration):
        self.log.debug("Wait for %sms from %sms" % (duration, self.duration))
        self.duration += duration
        self.steps.append((self.instances, int(duration) / 1000))
        return self

    def ramp(self, count, duration):
        self.log.debug(
            "Ramp %s instances in %sms from %sms" %
            (count, duration, self.duration))
        if count < 0:
            raise StepperConfigurationError(
                "Can not stop instances in instances_schedule.")
        interval = float(duration) / (count - 1)
        start_time = self.duration
        self.generators.append(
            int(start_time + i * interval) for i in range(0, count))
        self.steps += [(self.instances + i + 1, int(interval / 1000.0))
                       for i in range(0, count)]
        self.instances += count
        self.duration += duration
        return self

    def const(self, instances, duration):
        self.start(instances - self.instances)
        self.wait(duration)
        return self

    def line(self, initial_instances, final_instances, duration):
        self.start(initial_instances - self.instances - 1)
        self.ramp(final_instances - initial_instances + 1, duration)
        return self

    def stairway(
            self, initial_instances, final_instances, step_size, step_duration):
        step_count = (final_instances - initial_instances) // step_size
        self.log.debug("Making a stairway: %s steps" % step_count)
        self.start(initial_instances - self.instances)
        for i in range(1, step_count + 1):
            self.wait(step_duration).start(step_size)
        if final_instances != self.instances:
            self.wait(step_duration).start(final_instances - self.instances)
        self.wait(step_duration)
        return self

    def add_step(self, step_config):
        def parse_ramp(params):
            template = re.compile('(\d+),\s*([0-9.]+[dhms]?)+\)')
            s_res = template.search(params)
            if s_res:
                instances, interval = s_res.groups()
                self.ramp(int(instances), parse_duration(interval))
            else:
                self.log.info(
                    "Ramp step format: 'ramp(<instances_to_start>, <step_duration>)'"
                )
                raise StepperConfigurationError(
                    "Error in step configuration: 'ramp(%s'" % params)

        def parse_const(params):
            template = re.compile('(\d+),\s*([0-9.]+[dhms]?)+\)')
            s_res = template.search(params)
            if s_res:
                instances, interval = s_res.groups()
                self.const(int(instances), parse_duration(interval))
            else:
                self.log.info(
                    "Const step format: 'const(<instances_count>, <step_duration>)'"
                )
                raise StepperConfigurationError(
                    "Error in step configuration: 'const(%s'" % params)

        def parse_start(params):
            template = re.compile('(\d+)\)')
            s_res = template.search(params)
            if s_res:
                instances = s_res.groups()
                self.start(int(instances))
            else:
                self.log.info("Start step format: 'start(<instances_count>)'")
                raise StepperConfigurationError(
                    "Error in step configuration: 'start(%s'" % params)

        def parse_line(params):
            template = re.compile('(\d+),\s*(\d+),\s*([0-9.]+[dhms]?)+\)')
            s_res = template.search(params)
            if s_res:
                initial_instances, final_instances, interval = s_res.groups()
                self.line(
                    int(initial_instances),
                    int(final_instances), parse_duration(interval))
            else:
                self.log.info(
                    "Line step format: 'line(<initial_instances>, <final_instances>, <step_duration>)'"
                )
                raise StepperConfigurationError(
                    "Error in step configuration: 'line(%s'" % params)

        def parse_wait(params):
            template = re.compile('([0-9.]+[dhms]?)+\)')
            s_res = template.search(params)
            if s_res:
                duration = s_res.groups()[0]
                self.wait(parse_duration(duration))
            else:
                self.log.info("Wait step format: 'wait(<step_duration>)'")
                raise StepperConfigurationError(
                    "Error in step configuration: 'wait(%s'" % params)

        def parse_stairway(params):
            template = re.compile(
                '(\d+),\s*(\d+),\s*(\d+),\s*([0-9.]+[dhms]?)+\)')
            s_res = template.search(params)
            if s_res:
                initial_instances, final_instances, step_size, step_duration = s_res.groups(
                )
                self.stairway(
                    int(initial_instances),
                    int(final_instances),
                    int(step_size), parse_duration(step_duration))
            else:
                self.log.info(
                    "Stairway step format: 'step(<initial_instances>, <final_instances>, <step_size>, <step_duration>)'"
                )
                raise StepperConfigurationError(
                    "Error in step configuration: 'step(%s'" % params)

        _plans = {
            'line': parse_line,
            'const': parse_const,
            'step': parse_stairway,
            'ramp': parse_ramp,
            'wait': parse_wait,
            'start': parse_start,
        }
        step_type, params = step_config.split('(')
        step_type = step_type.strip()
        if step_type in _plans:
            _plans[step_type](params)
        else:
            raise NotImplementedError(
                'No such load type implemented for instances_schedule: "%s"' %
                step_type)

    def add_all_steps(self, steps):
        for step in steps:
            self.add_step(step)
        return self

    def create(self):
        self.generators.append(cycle([0]))
        return chain(*self.generators)


def create(instances_schedule):
    '''
    Creates load plan timestamps generator

    >>> from util import take

    >>> take(7, LoadPlanBuilder().ramp(5, 4000).create())
    [0, 1000, 2000, 3000, 4000, 0, 0]

    >>> take(7, create(['ramp(5, 4s)']))
    [0, 1000, 2000, 3000, 4000, 0, 0]

    >>> take(12, create(['ramp(5, 4s)', 'wait(5s)', 'ramp(5,4s)']))
    [0, 1000, 2000, 3000, 4000, 9000, 10000, 11000, 12000, 13000, 0, 0]

    >>> take(7, create(['wait(5s)', 'ramp(5, 0)']))
    [5000, 5000, 5000, 5000, 5000, 0, 0]

    >>> take(7, create([]))
    [0, 0, 0, 0, 0, 0, 0]

    >>> take(12, create(['line(1, 9, 4s)']))
    [0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 0, 0, 0]

    >>> take(12, create(['const(3, 5s)', 'line(7, 11, 2s)']))
    [0, 0, 0, 5000, 5000, 5000, 5000, 5500, 6000, 6500, 7000, 0]

    >>> take(12, create(['step(2, 10, 2, 3s)']))
    [0, 0, 3000, 3000, 6000, 6000, 9000, 9000, 12000, 12000, 0, 0]

    >>> take(12, LoadPlanBuilder().const(3, 1000).line(5, 10, 5000).steps)
    [(3, 1), (5, 1), (6, 1), (7, 1), (8, 1), (9, 1), (10, 1)]

    >>> take(12, LoadPlanBuilder().stairway(100, 950, 100, 30000).steps)
    [(100, 30), (200, 30), (300, 30), (400, 30), (500, 30), (600, 30), (700, 30), (800, 30), (900, 30), (950, 30)]

    >>> LoadPlanBuilder().stairway(100, 950, 100, 30000).instances
    950

    >>> LoadPlanBuilder().const(3, 1000).line(5, 10, 5000).instances
    10

    >>> LoadPlanBuilder().line(1, 100, 60000).instances
    100
    '''
    lpb = LoadPlanBuilder().add_all_steps(instances_schedule)
    lp = lpb.create()
    info.status.publish('duration', 0)
    # info.status.publish('steps', lpb.steps)
    info.status.publish('steps', [])
    info.status.publish('instances', lpb.instances)
    return lp
