'''
Utilities: parsers, converters, etc.
'''
import re
import logging
import math
from itertools import islice

from .module_exceptions import StepperConfigurationError

logging.getLogger("requests").setLevel(logging.WARNING)


def take(number, iter):
    return list(islice(iter, 0, number))


def parse_duration(duration):
    '''
    Parse duration string, such as '3h2m3s' into milliseconds

    >>> parse_duration('3h2m3s')
    10923000

    >>> parse_duration('0.3s')
    300

    >>> parse_duration('5')
    5000
    '''
    _re_token = re.compile("([0-9.]+)([dhms]?)")

    def parse_token(time, multiplier):
        multipliers = {
            'd': 86400,
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
            return int(float(time) * 1000)

    return sum(parse_token(*token) for token in _re_token.findall(duration))


def solve_quadratic(a, b, c):
    '''
    >>> solve_quadratic(1.0, 2.0, 1.0)
    (-1.0, -1.0)
    '''
    discRoot = math.sqrt((b * b) - 4 * a * c)
    root1 = (-b - discRoot) / (2 * a)
    root2 = (-b + discRoot) / (2 * a)
    return (root1, root2)


def s_to_ms(f_sec):
    return int(f_sec * 1000.0)


def proper_round(n):
    """
    rounds float to closest int
    :rtype: int
    :param n: float
    """
    return int(n) + (n / abs(n)) * int(abs(n - int(n)) >= 0.5) if n != 0 else 0
