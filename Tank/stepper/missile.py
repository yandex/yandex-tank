'''
Missile object and generators

You should update Stepper.status.ammo_count and Stepper.status.loop_count in your custom generators!
'''
from itertools import cycle
from module_exceptions import AmmoFileError
import os.path
import info
import logging
import re


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
            info.status.inc_loop_count()
            info.status.inc_ammo_count()  # loops equals ammo count
            yield m


class UriStyleGenerator(object):

    '''
    Generates GET ammo based on given URI list.
    '''

    def __init__(self, uris, headers, http_ver='1.1'):
        '''
        uris - a list of URIs as strings.
        '''
        self.uri_count = len(uris)
        self.missiles = cycle(
            [(HttpAmmo(uri, headers, http_ver=http_ver).to_s(), None) for uri in uris])

    def __iter__(self):
        for m in self.missiles:
            info.status.inc_ammo_count()
            info.status.loop_count = info.status.ammo_count / self.uri_count
            yield m


class AmmoFileReader(object):

    '''Read missiles from ammo file'''

    def __init__(self, filename):
        self.filename = filename
        self.log = logging.getLogger(__name__)
        self.log.info("Loading ammo from '%s'" % filename)

    def __iter__(self):
        def read_chunk_header(ammo_file):
            chunk_header = ''
            while chunk_header is '':
                line = ammo_file.readline()
                if line is '':
                    return line
                chunk_header = line.strip('\r\n')
            return chunk_header
        with open(self.filename, 'rb') as ammo_file:
            info.status.af_size = os.path.getsize(self.filename)
            chunk_header = read_chunk_header(ammo_file) #  if we got StopIteration here, the file is empty
            while chunk_header:
                if chunk_header is not '':
                    try:
                        fields = chunk_header.split()
                        chunk_size = int(fields[0])
                        marker = fields[1] if len(fields) > 1 else None
                        missile = ammo_file.read(chunk_size)
                        if len(missile) < chunk_size:
                            raise AmmoFileError(
                                "Unexpected end of file: read %s bytes instead of %s" % (len(missile), chunk_size))
                        info.status.inc_ammo_count()
                        yield (missile, marker)
                    except (IndexError, ValueError) as e:
                        raise AmmoFileError(
                            "Error while reading ammo file. Position: %s, header: '%s', original exception: %s" % (ammo_file.tell(), chunk_header, e))
                chunk_header = read_chunk_header(ammo_file)
                if chunk_header == '':
                    self.log.debug('Reached the end of ammo file. Starting over.')
                    ammo_file.seek(0)
                    info.status.inc_loop_count()
                    chunk_header = read_chunk_header(ammo_file)
                info.status.af_position = ammo_file.tell()


class SlowLogReader(object):

    '''Read missiles from SQL slow log. Not usable with Phantom'''

    def __init__(self, filename):
        self.filename = filename

    def __iter__(self):
        with open(self.filename, 'rb') as ammo_file:
            info.status.af_size = os.path.getsize(self.filename)
            request = ""
            use_db = ""
            loop_count = 0
            while True:
                for line in ammo_file:
                    info.status.af_position = ammo_file.tell()
                    if line.startswith('#') or line.startswith('/*'):
                        pass
                    else:
                        if line.startswith('use'):
                            use_db = line
                        else:
                            line = line.rstrip('\r\n')
                            if line.endswith(';'):
                                req_end = line.rstrip(';\r\n')
                                result = ' '.join((request + req_end).split())
                                for kw in 'select insert update delete'.split():
                                    if result.startswith(kw):
                                        info.status.inc_ammo_count()
                                        yield (use_db + result, None)
                                        break
                                request = ""
                            else:
                                request += line
                loop_count += 1
                ammo_file.seek(0)
                info.status.af_position = 0
                info.status.inc_loop_count()