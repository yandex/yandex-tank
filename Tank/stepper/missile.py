'''
Missile generator
'''
from itertools import cycle
from exceptions import AmmoFileError


class HttpAmmo(object):
    def __init__(self, uri, headers, method='GET', http_ver='1.1'):
        self.method = method
        self.uri = uri
        self.proto = 'HTTP/%s' % http_ver
        self.headers = headers
        self.body = []
        self.loops = 0

    def to_s(self):
        return "%s %s %s\n%s" % (self.method, self.uri, self.proto, '\n'.join(self.headers))


class SimpleGenerator(object):
    '''Generates ammo based on given sample'''
    def __init__(self, missile_sample):
        self.missiles = cycle([(missile_sample.to_s(), None)])

    def __iter__(self):
        for m in self.missiles:
            self.loops += 1
            yield m

    def loop_count(self):
        return self.loops


class UriStyleGenerator(SimpleGenerator):
    '''Generates GET ammo based on given URI list'''
    def __init__(self, uris, headers, loop_limit=0, http_ver='1.1'):
        self.ammo_number = 0
        self.loop_limit = loop_limit
        self.uri_count = len(uris)
        self.missiles = cycle([(HttpAmmo(uri, headers, http_ver).to_s(), None) for uri in uris])

    def __iter__(self):
        for m in self.missiles:
            self.ammo_number += 1
            if self.loop_limit and self.loop_count() > self.loop_limit:
                raise StopIteration
            else:
                yield m

    def loop_count(self):
        return self.ammo_number / self.uri_count


class AmmoFileReader(SimpleGenerator):
    '''Read missiles from ammo file'''
    def __init__(self, filename, loop_limit=0):
        self.filename = filename
        self.loops = 0
        self.loop_limit = loop_limit

    def __iter__(self):
        with open(self.filename, 'rb') as ammo_file:
            chunk_header = ammo_file.readline()
            while chunk_header:
                try:
                    fields = chunk_header.split()
                    chunk_size = int(fields[0])
                    marker = fields[1] if len(fields) > 1 else None
                    missile = ammo_file.read(chunk_size)
                    if len(missile) < chunk_size:
                        raise AmmoFileError("Unexpected end of file: read %s bytes instead of %s" % (len(missile), chunk_size))
                    yield (missile, marker)
                except (IndexError, ValueError):
                    raise AmmoFileError("Error while reading ammo file. Position: %s, header: '%s'" % (ammo_file.tell(), chunk_header))
                chunk_header = ammo_file.readline()
                if not chunk_header and (self.loops < self.loop_limit or self.loop_limit == 0):
                    self.loops += 1
                    ammo_file.seek(0)
                    chunk_header = ammo_file.readline()
