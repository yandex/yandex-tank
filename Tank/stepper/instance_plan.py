from itertools import cycle, repeat, chain
from util import parse_duration
from module_exceptions import StepperConfigurationError
import re
import info
import logging


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
        self.steps.append((self.instances, duration / 1000.0))
        return self

    def ramp(self, count, duration):
        self.log.debug("Ramp %s instances in %sms from %sms" %
                       (count, duration, self.duration))
        if count < 0:
            raise StepperConfigurationError(
                "Can not stop instances in instances_schedule.")
        interval = float(duration) / count
        start_time = self.duration
        self.generators.append(int(start_time + i * interval)
                               for i in xrange(0, count))
        self.steps += [(self.instances + i, interval / 1000.0) for i in xrange(0, count)]
        self.instances += count
        self.duration += duration
        return self

    def const(self, instances, duration):
        self.start(instances - self.instances)
        self.wait(duration)
        return self

    def line(self, initial_instances, final_instances, duration):
        self.start(initial_instances - self.instances)
        self.ramp(final_instances - initial_instances, duration)
        return self

    def stairway(self, initial_instances, final_instances, step_size, step_duration):
        self.start(initial_instances - self.instances)
        step_count = (final_instances - initial_instances) / step_size
        self.log.debug("Making a stairway: %s steps" % step_count)
        for i in xrange(1, step_count):
            self.wait(step_duration).start(step_size)
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
                    "Ramp step format: 'ramp(<instances_to_start>, <step_duration>)'")
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
                    "Const step format: 'const(<instances_count>, <step_duration>)'")
                raise StepperConfigurationError(
                    "Error in step configuration: 'const(%s'" % params)

        def parse_line(params):
            template = re.compile('(\d+),\s*(\d+),\s*([0-9.]+[dhms]?)+\)')
            s_res = template.search(params)
            if s_res:
                initial_instances, final_instances, interval = s_res.groups()
                self.line(
                    int(initial_instances),
                    int(final_instances),
                    parse_duration(interval)
                )
            else:
                self.log.info(
                    "Line step format: 'line(<initial_instances>, <final_instances>, <step_duration>)'")
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
                self.stairway(int(initial_instances), int(final_instances), int(
                    step_size), parse_duration(step_duration))
            else:
                self.log.info(
                    "Stairway step format: 'step(<initial_instances>, <final_instances>, <step_size>, <step_duration>)'")
                raise StepperConfigurationError(
                    "Error in step configuration: 'step(%s'" % params)

        _plans = {
            'line': parse_line,
            'const': parse_const,
            'step': parse_stairway,
            'ramp': parse_ramp,
            'wait': parse_wait,
        }
        step_type, params = step_config.split('(')
        step_type = step_type.strip()
        if step_type in _plans:
            _plans[step_type](params)
        else:
            raise NotImplementedError(
                'No such load type implemented for instances_schedule: "%s"' % step_type)

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

    >>> take(7, LoadPlanBuilder().ramp(5, 5000).create())
    [0, 1000, 2000, 3000, 4000, 0, 0]

    >>> take(7, create(['ramp(5, 5s)']))
    [0, 1000, 2000, 3000, 4000, 0, 0]

    >>> take(12, create(['ramp(5, 5s)', 'wait(5s)', 'ramp(5,5s)']))
    [0, 1000, 2000, 3000, 4000, 10000, 11000, 12000, 13000, 14000, 0, 0]

    >>> take(7, create(['wait(5s)', 'ramp(5, 0)']))
    [5000, 5000, 5000, 5000, 5000, 0, 0]

    >>> take(7, create([]))
    [0, 0, 0, 0, 0, 0, 0]

    >>> take(12, create(['const(3, 5s)', 'line(7, 10, 5s)']))
    [0, 0, 0, 5000, 5000, 5000, 5000, 5000, 6666, 8333, 0, 0]

    >>> take(10, create(['step(2, 10, 2, 3s)']))
    [0, 0, 3000, 3000, 6000, 6000, 9000, 9000, 0, 0]

    >>> take(12, LoadPlanBuilder().const(3, 1000).line(5, 10, 5000).steps)
    [(3, 1.0), (5, 1.0), (6, 1.0), (7, 1.0), (8, 1.0), (9, 1.0)]
    '''
    lpb = LoadPlanBuilder().add_all_steps(instances_schedule)
    info.status.publish('duration', 0)
    info.status.publish('steps', lpb.steps)
    info.status.publish('instances', lpb.instances)
    return lpb.create()
