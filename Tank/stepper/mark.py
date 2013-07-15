from uuid import uuid4

__test_missile = """\
POST /advq/search HTTP/1.1\r
Connection: close\r
Host: ust1-1.advq.yandex.ru\r
Content-length: 163\r
\r
ph_page_size=50&ph_page=0&words=%22%21%D1%81%D0%BA%D0%B0%D1%87%D0%B0%D1%82%D1%8C+%21pelingator+%211.07+%21%D0%B1%D0%B5%D1%81%D0%BF%D0%BB%D0%B0%D1%82%D0%BD%D0%BE%22
"""


def __mark_by_uri(missile):
    return '_'.join(missile.split('\n', 1)[0].split(' ', 2)[1].split('/'))


__markers = {
    'uniq': lambda m: uuid4().hex,
    'uri': __mark_by_uri,
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
    '_advq_search'

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
        return lambda m: 'None'
