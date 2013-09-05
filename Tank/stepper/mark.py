from uuid import uuid4

__test_missile = """\
POST /example/search HTTP/1.1\r
Connection: close\r
Host: example.org\r
Content-length: 32\r
\r
param1=50&param2=0&param3=hello
"""

__test_missile = """\
GET /example/search?param1=50&param2=0&param3=hello HTTP/1.1\r
Connection: close\r
Host: example.org\r
Content-length: 32\r
\r
"""


def __mark_by_uri(missile):
    return '_'.join(missile.split('\n', 1)[0].split(' ', 2)[1].split('?')[0].split('/'))


__markers = {
    'uniq': lambda m: uuid4().hex,
    'uri': __mark_by_uri,
    '1': __mark_by_uri,
}


def get_marker(marker_type):
    '''
    Returns a marker function of the requested marker_type

    >>> marker = get_marker('uniq')(__test_missile)
    >>> type(marker)
    <type 'str'>
    >>> len(marker)
    32

    >>> get_marker('uri')(__test_missile)
    '_example_search'

    >>> marker = get_marker('non-existent')(__test_missile)
    Traceback (most recent call last):
      ...
    NotImplementedError: No such marker: "non-existent"

    '''
    if marker_type and marker_type is not '0':
        if marker_type in __markers:
            return __markers[marker_type]
        else:
            raise NotImplementedError(
                'No such marker: "%s"' % marker_type)
    else:
        return lambda m: ''
