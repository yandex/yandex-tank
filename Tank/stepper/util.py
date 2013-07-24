'''
Utilities: parsers, converters, etc.
'''
import re
from itertools import islice
from module_exceptions import StepperConfigurationError


def take(number, iter):
    return list(islice(iter, 0, number))


def parse_duration(duration):
    '''
    Parse duration string, such as '3h2m3s' into milliseconds

    >>> parse_duration('3h2m3s')
    10923000

    >>> parse_duration('0.3s')
    300
    '''
    _re_token = re.compile("([0-9.]+)([dhms]?)")

    def parse_token(time, multiplier):
        multipliers = {
            'h': 3600,
            'm': 60,
            's': 1,
        }
        if multiplier:
            if multiplier in multipliers:
                return int(float(time) * multipliers[multiplier] * 1000)
            else:
                raise StepperConfigurationError(
                    'Failed to parse duration: %s' % duration)
        else:
            return int(time * 1000)

    return sum(parse_token(*token) for token in _re_token.findall(duration))


class Limiter(object):

    def __init__(self, gen, limit):
        self.gen = islice(gen, limit)
        self.limit = limit

    def __len__(self):
        return self.limit

    def __iter__(self):
        return (item for item in self.gen)

    def loop_count(self):
        return 0


def limiter(gen, limit):
    if limit == 0:
        return gen
    else:
        return Limiter(gen, limit)
