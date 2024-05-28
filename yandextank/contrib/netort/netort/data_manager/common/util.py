import collections
import time
import logging
import os
import re
import yaml

# TODO: rename to format_http_request
from threading import Lock


def pretty_print(req):
    return '{header}\n{query}\n{http_headers}\n\n{body}\n{footer}'.format(
        header='-----------QUERY START-----------',
        query=req.method + ' ' + req.url,
        http_headers='\n'.join('{}: {}'.format(k, v) for k, v in req.headers.items()),
        body=req.body,
        footer='-----------QUERY END-----------'
    )


def recursive_dict_update(d1, d2):
    for k, v in d2.items():
        if isinstance(v, collections.Mapping):
            r = recursive_dict_update(d1.get(k, {}), v)
            d1[k] = r
        else:
            d1[k] = d2[k]
    return d1


def log_time_decorator(func):
    """
    logs func execution time
    :param func:
    :return:
    """
    def timed(*args, **kwargs):
        start = time.time()
        res = func(*args, **kwargs)
        logging.debug('TIMER {}: {}'.format(func.__name__, round(time.time() - start, 3)))
        return res

    return timed


class thread_safe_property(object):
    # credits to https://stackoverflow.com/a/39217007/3316574
    def __init__(self, func):
        self._func = func
        self.__name__ = func.__name__
        self.__doc__ = func.__doc__
        self._lock = Lock()

    def __get__(self, obj, klass=None):
        if obj is None:
            return None
        # __get__ may be called concurrently
        with self._lock:
            # another thread may have computed property value
            # while this thread was in __get__
            if self.__name__ not in obj.__dict__:
                # none computed `_func` yet, do so (under lock) and set attribute
                obj.__dict__[self.__name__] = self._func(obj)
        # by now, attribute is guaranteed to be set,
        # either by this thread or another
        return obj.__dict__[self.__name__]


def expandvars(path, default=None):
    if default is None:
        return os.path.expandvars(path)

    # matches expressions like ${VALUE} where VALUE is parsed to group 1
    reVar = r'\$\{([^}]*)\}'

    def replace_var(m: re.Match):
        return os.environ.get(m.group(1), default)

    return re.sub(reVar, replace_var, path)


def env_constructor(loader, node):
    return expandvars(node.value, default='')


class YamlEnvSubstConfigLoader(yaml.SafeLoader):
    pass


env_matcher = re.compile(r'.*\$\{([^}^{]+)\}.*')
YamlEnvSubstConfigLoader.add_implicit_resolver('!env', env_matcher, None)
YamlEnvSubstConfigLoader.add_constructor('!env', constructor=env_constructor)
