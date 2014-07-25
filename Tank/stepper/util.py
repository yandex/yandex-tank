'''
Utilities: parsers, converters, etc.
'''
import re
import logging
from itertools import islice
from module_exceptions import StepperConfigurationError
import math
import gzip


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


def get_opener(f_path):
    """ Returns opener function according to file extensions:
        bouth open and gzip.open calls return fileobj.

    Args:
        f_path: str, ammo file path.

    Returns:
        function, to call for file open.
    """
    if f_path.endswith('.gz'):
        logging.info("Using gzip opener")
        return gzip.open
    else:
        return open
