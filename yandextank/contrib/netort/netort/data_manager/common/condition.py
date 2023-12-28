import fnmatch
import typing
from urllib.parse import urlparse


class Condition(object):
    def __init__(self, callable_: typing.Callable, explanation: str):
        self._callable = callable_
        self._explanation = explanation

    def __call__(self, *args, **kwargs):
        return self._callable(*args, **kwargs)

    def __repr__(self) -> str:
        return self._explanation

    def __str__(self) -> str:
        return self.__repr__()


def uri_like(
    *,
    scheme: typing.Optional[str] = None,
    host: typing.Optional[str] = None,
    path: typing.Optional[str] = None,
) -> Condition:
    if all(arg is None for arg in [scheme, host, path]):
        raise ValueError('uri_like: at least one argument must be specified')

    def condition(url: str, *args, **kwargs):
        parsed = urlparse(url)
        meet = True
        if scheme is not None:
            meet = meet and parsed.scheme.lower() == scheme.lower()
        if host is not None:
            meet = meet and _host_match(parsed.netloc, host)
        if path is not None:
            meet = meet and fnmatch.fnmatch(parsed.path.lower(), path.lower())
        return meet

    explanation = '/'.join(filter(None, [
        f'{scheme}:/' if scheme is not None else 'scheme:/',
        host if host is not None else '*',
        path,
    ]))
    return Condition(condition, f'uri like {explanation}')


def and_(*conditions) -> Condition:
    explanation = ' and '.join([repr(c) for c in conditions])
    return Condition(lambda *args, **kwargs: all([c(*args, **kwargs) for c in conditions]), explanation)


def path_like(pattern: str) -> Condition:
    def condition(path: str, *args, **kwargs):
        return fnmatch.fnmatchcase(path, pattern)
    return Condition(condition, f'path_like "{pattern}"')


def _host_match(netloc: str, pattern: str) -> bool:
    netloc_host = netloc.rsplit(':', 1)[0]
    return fnmatch.fnmatch(netloc_host, pattern)
