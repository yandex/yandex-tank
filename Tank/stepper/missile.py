'''
Missile object and generators
'''
from itertools import cycle
from module_exceptions import AmmoFileError
from info import STATUS


class HttpAmmo(object):

    '''
    Represents HTTP missile
    '''

    def __init__(self, uri, headers, method='GET', http_ver='1.1'):
        self.method = method
        self.uri = uri
        self.proto = 'HTTP/%s' % http_ver
        self.headers = headers
        self.body = []

    def to_s(self):
        if self.headers:
            headers = '\r\n'.join(self.headers) + '\r\n'
        else:
            headers = ''
        return "%s %s %s\r\n%s\r\n" % (self.method, self.uri, self.proto, headers)


class SimpleGenerator(object):

    '''
    Generates ammo based on a given sample.
    '''

    def __init__(self, missile_sample):
        '''
        Missile sample is any object that has to_s method which
        returns its string representation.
        '''
        self.missiles = cycle([(missile_sample.to_s(), None)])

    def __iter__(self):
        for m in self.missiles:
            self.loops += 1
            STATUS.publish('loop_count', self.loops)
            STATUS.publish('ammo_count', self.loops)  # loops equals ammo count
            yield m

    def loop_count(self):
        return self.loops


class UriStyleGenerator(SimpleGenerator):

    '''
    Generates GET ammo based on given URI list.
    '''

    def __init__(self, uris, headers, loop_limit=0, http_ver='1.1'):
        '''
        uris - a list of URIs as strings.
        '''
        self.ammo_count = 0
        self.loop_count = 0
        self.loop_limit = loop_limit
        self.uri_count = len(uris)
        self.missiles = cycle(
            [(HttpAmmo(uri, headers, http_ver=http_ver).to_s(), None) for uri in uris])

    def __iter__(self):
        for m in self.missiles:
            self.ammo_count += 1
            STATUS.publish('ammo_count', self.ammo_count)
            self.update_loop_count()
            if self.loop_limit and self.loop_count > self.loop_limit:
                raise StopIteration
            else:
                yield m

    def update_loop_count(self):
        loop_count = self.ammo_count / self.uri_count
        if self.loop_count != loop_count:
            STATUS.publish('loop_count', loop_count)
            self.loop_count = loop_count


class AmmoFileReader(SimpleGenerator):

    '''Read missiles from ammo file'''

    def __init__(self, filename, loop_limit=0):
        self.filename = filename
        self.loops = 0
        self.loop_limit = loop_limit

    def __iter__(self):
        with open(self.filename, 'rb') as ammo_file:
            ammo_count = 0
            chunk_header = ammo_file.readline()
            while chunk_header:
                if chunk_header.strip('\r\n') is not '':
                    try:
                        fields = chunk_header.split()
                        chunk_size = int(fields[0])
                        marker = fields[1] if len(fields) > 1 else None
                        missile = ammo_file.read(chunk_size)
                        if len(missile) < chunk_size:
                            raise AmmoFileError(
                                "Unexpected end of file: read %s bytes instead of %s" % (len(missile), chunk_size))
                        ammo_count += 1
                        STATUS.publish('ammo_count', ammo_count)
                        yield (missile, marker)
                    except (IndexError, ValueError):
                        raise AmmoFileError(
                            "Error while reading ammo file. Position: %s, header: '%s'" % (ammo_file.tell(), chunk_header))
                chunk_header = ammo_file.readline()
                if not chunk_header and (self.loops < self.loop_limit or self.loop_limit == 0):
                    self.loops += 1
                    STATUS.publish('loop_count', self.loops)
                    ammo_file.seek(0)
                    chunk_header = ammo_file.readline()
