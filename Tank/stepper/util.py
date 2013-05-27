'''
Utilities: parsers, converters, etc.
'''
import re
from itertools import islice
from exceptions import StepperConfigurationError


def parse_duration(duration):
    '''
    Parse duration string, such as '3h2m3s'
    '''
    _re_token = re.compile("(\d+)([dhms]?)")

    def parse_token(time, multiplier):
        multipliers = {
            'h': 3600,
            'm': 60,
            's': 1,
        }
        if multiplier:
            if multiplier in multipliers:
                return int(time) * multipliers[multiplier]
            else:
                raise StepperConfigurationError('Failed to parse duration: %s' % duration)
        else:
            return int(time)

    return sum(parse_token(*token) for token in _re_token.findall(duration))


class Limiter(object):
    def __init__(self, gen, limit):
        self.limit = limit or 0
        if not limit:
            self.gen = gen
        else:
            self.gen = islice(gen, limit)

    def __len__(self):
        return self.limit

    def __iter__(self):
        return (item for item in self.gen)
