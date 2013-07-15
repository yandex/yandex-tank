from uuid import uuid4


def __mark_by_uri(missile):
    return missile.split('\n', 1)[0].split(' ', 2)[1].split('?', 1)[0]


__markers = {
    'uniq': lambda m: uuid4().hex,
    'uri': __mark_by_uri,
}


def get_marker(marker_type):
    if marker_type and marker_type is not '0':
        if marker_type in __markers:
            return __markers[marker_type]
        else:
            raise NotImplementedError(
                'No such marker: "%s"' % marker_type)
    else:
        return lambda m: 'None'
