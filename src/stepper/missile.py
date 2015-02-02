'''
Missile object and generators

You should update Stepper.status.ammo_count and Stepper.status.loop_count in your custom generators!
'''
from util import get_opener
from itertools import cycle
from module_exceptions import AmmoFileError
import os.path
import info
import logging


class HttpAmmo(object):
    '''
    Represents HTTP missile

    >>> print HttpAmmo('/', []).to_s()  # doctest: +NORMALIZE_WHITESPACE
    GET / HTTP/1.1

    >>> print HttpAmmo('/', ['Connection: Close', 'Content-Type: Application/JSON']).to_s()  # doctest: +NORMALIZE_WHITESPACE
    GET / HTTP/1.1
    Connection: Close
    Content-Type: Application/JSON

    >>> print HttpAmmo('/', ['Connection: Close'], method='POST', body='hello!').to_s()  # doctest: +NORMALIZE_WHITESPACE
    POST / HTTP/1.1
    Connection: Close
    Content-Length: 6
    <BLANKLINE>
    hello!
    '''

    def __init__(self, uri, headers, method='GET', http_ver='1.1', body=''):
        self.method = method
        self.uri = uri
        self.proto = 'HTTP/%s' % http_ver
        self.headers = set(headers)
        self.body = body
        if len(body):
            self.headers.add("Content-Length: %s" % len(body))

    def to_s(self):
        if self.headers:
            headers = '\r\n'.join(self.headers) + '\r\n'
        else:
            headers = ''
        return "%s %s %s\r\n%s\r\n%s" % (self.method, self.uri, self.proto, headers, self.body)


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
            yield m
            info.status.loop_count = info.status.ammo_count / self.uri_count


class AmmoFileReader(object):

    '''Read missiles from ammo file'''

    def __init__(self, filename, **kwargs):
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
        with get_opener(self.filename)(self.filename, 'rb') as ammo_file:
            info.status.af_size = os.path.getsize(self.filename)
            chunk_header = read_chunk_header(ammo_file) #  if we got StopIteration here, the file is empty
            while chunk_header:
                if chunk_header is not '':
                    try:
                        fields = chunk_header.split()
                        chunk_size = int(fields[0])
                        if chunk_size == 0:
                            if info.status.loop_count == 0:
                                self.log.info('Zero-sized chunk in ammo file at %s. Starting over.' % ammo_file.tell())
                            ammo_file.seek(0)
                            info.status.inc_loop_count()
                            chunk_header = read_chunk_header(ammo_file)
                            continue
                        marker = fields[1] if len(fields) > 1 else None
                        missile = ammo_file.read(chunk_size)
                        if len(missile) < chunk_size:
                            raise AmmoFileError(
                                "Unexpected end of file: read %s bytes instead of %s" % (len(missile), chunk_size))
                        yield (missile, marker)
                    except (IndexError, ValueError) as e:
                        raise AmmoFileError(
                            "Error while reading ammo file. Position: %s, header: '%s', original exception: %s" % (ammo_file.tell(), chunk_header, e))
                chunk_header = read_chunk_header(ammo_file)
                if chunk_header == '':
                    ammo_file.seek(0)
                    info.status.inc_loop_count()
                    chunk_header = read_chunk_header(ammo_file)
                info.status.af_position = ammo_file.tell()


class SlowLogReader(object):

    '''Read missiles from SQL slow log. Not usable with Phantom'''

    def __init__(self, filename, **kwargs):
        self.filename = filename

    def __iter__(self):
        with open(self.filename, 'rb') as ammo_file:
            info.status.af_size = os.path.getsize(self.filename)
            request = ""
            while True:
                for line in ammo_file:
                    info.status.af_position = ammo_file.tell()
                    if line.startswith('#'):
                        if request != "":
                            yield (request, None)
                            request = ""
                    else:
                        request += line
                ammo_file.seek(0)
                info.status.af_position = 0
                info.status.inc_loop_count()

class LineReader(object):

    '''One line -- one missile'''

    def __init__(self, filename, **kwargs):
        self.filename = filename

    def __iter__(self):
        with get_opener(self.filename)(self.filename, 'rb') as ammo_file:
            while True:
                for line in ammo_file:
                    info.status.af_position = ammo_file.tell()
                    yield (line.rstrip('\r\n'), None)
                ammo_file.seek(0)
                info.status.af_position = 0
                info.status.inc_loop_count()


class AccessLogReader(object):

    '''Missiles from access log'''

    def __init__(self, filename, headers=[], http_ver='1.1', **kwargs):
        self.filename = filename
        self.warned = False
        self.headers = set(headers)
        self.log = logging.getLogger(__name__)

    def warn(self, message):
        if not self.warned:
            self.warned = True
            self.log.warning("There are some skipped lines. See full log for details.")
        self.log.debug(message)

    def __iter__(self):
        with get_opener(self.filename)(self.filename, 'rb') as ammo_file:
            while True:
                for line in ammo_file:
                    info.status.af_position = ammo_file.tell()
                    try:
                        request = line.split('"')[1]
                        method, uri, proto = request.split()
                        http_ver = proto.split('/')[1]
                        if method == "GET":
                            yield (
                                HttpAmmo(
                                    uri,
                                    headers=self.headers,
                                    http_ver=http_ver,
                                ).to_s(), None)
                        else:
                            self.warn("Skipped line: %s (unsupported method)" % line)
                    except (ValueError, IndexError), e:
                        self.warn("Skipped line: %s (%s)" % (line, e))
                    
                ammo_file.seek(0)
                info.status.af_position = 0
                info.status.inc_loop_count()


class UriReader(object):
    def __init__(self, filename, headers=[], http_ver='1.1', **kwargs):
        self.filename = filename
        self.headers = set(headers)
        self.http_ver = http_ver
        self.log = logging.getLogger(__name__)
        self.log.info("Loading ammo from '%s' using URI format." % filename)

    def __iter__(self):
        with get_opener(self.filename)(self.filename, 'rb') as ammo_file:
            while True:
                for line in ammo_file:
                    info.status.af_position = ammo_file.tell()
                    if line.startswith('['):
                        self.headers.add(line.strip('\r\n[]\t '))
                    elif len(line.rstrip('\r\n')):
                        fields = line.split()
                        uri = fields[0]
                        if len(fields) > 1:
                            marker = fields[1]
                        else:
                            marker = None
                        yield (
                            HttpAmmo(
                                uri,
                                headers=self.headers,
                                http_ver=self.http_ver,
                            ).to_s(), marker)
                if info.status.ammo_count == 0:
                    self.log.error("No ammo in uri-style file")
                    raise AmmoFileError("No ammo! Cover me!")
                ammo_file.seek(0)
                info.status.af_position = 0
                info.status.inc_loop_count()

class UriPostReader(object):

    '''Read POST missiles from ammo file'''

    def __init__(self, filename, headers=[], http_ver='1.1', **kwargs):
        self.filename = filename
        self.headers = set(headers)
        self.http_ver = http_ver
        self.log = logging.getLogger(__name__)
        self.log.info("Loading ammo from '%s' using URI+POST format" % filename)

    def __iter__(self):
        def read_chunk_header(ammo_file):
            chunk_header = ''
            while chunk_header is '':
                line = ammo_file.readline()
                if line.startswith('['):
                        self.headers.add(line.strip('\r\n[]\t '))
                elif line is '':
                    return line
                else:
                    chunk_header = line.strip('\r\n')
            return chunk_header
        with get_opener(self.filename)(self.filename, 'rb') as ammo_file:
            info.status.af_size = os.path.getsize(self.filename)
            chunk_header = read_chunk_header(ammo_file) #  if we got StopIteration here, the file is empty
            while chunk_header:
                if chunk_header is not '':
                    try:
                        fields = chunk_header.split()
                        chunk_size = int(fields[0])
                        if chunk_size == 0:
                            self.log.debug('Zero-sized chunk in ammo file at %s. Starting over.' % ammo_file.tell())
                            ammo_file.seek(0)
                            info.status.inc_loop_count()
                            chunk_header = read_chunk_header(ammo_file)
                            continue
                        uri = fields[1]
                        marker = fields[2] if len(fields) > 2 else None
                        missile = ammo_file.read(chunk_size)
                        if len(missile) < chunk_size:
                            raise AmmoFileError(
                                "Unexpected end of file: read %s bytes instead of %s" % (len(missile), chunk_size))
                        yield (
                            HttpAmmo(
                                uri=uri,
                                headers=self.headers,
                                method='POST',
                                body=missile,
                                http_ver=self.http_ver,
                            ).to_s(),
                            marker
                        )
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