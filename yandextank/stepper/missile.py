'''
Missile object and generators

You should update Stepper.status.ammo_count and Stepper.status.loop_count in your custom generators!
'''
import logging
from itertools import cycle

from netort.resource import manager as resource

from . import info
from .info import LoopCountLimit
from .module_exceptions import AmmoFileError


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

    def __init__(self, uri, headers, method='GET', http_ver='1.1', body=b''):
        self.method = method
        self.uri = uri.encode('utf8') if isinstance(uri, str) else uri
        self.proto = 'HTTP/%s' % http_ver
        self.headers = set(headers)
        self.body = body
        if len(body):
            self.headers.add("Content-Length: %s" % len(body))

    def to_s(self):
        if self.headers:
            headers = b'\r\n'.join(sorted([h.encode('utf8') for h in self.headers])) + b'\r\n'
        else:
            headers = b''
        return b"%s %s %s\r\n%s\r\n%s" % (
            self.method.encode('utf8'),
            self.uri,
            self.proto.encode('utf8'),
            headers,
            self.body)


class UriStyleGenerator(object):
    """
    Generates GET ammo based on given URI list.
    """

    def __init__(self, uris, headers, http_ver='1.1'):
        """
        uris - a list of URIs as strings.
        """
        super().__init__()
        self.missiles = cycle(
            [(HttpAmmo(uri, headers, http_ver=http_ver).to_s(), None) for uri in uris] + [None]  # None marks loop end
        )

    def __iter__(self):
        for m in self.missiles:
            if m is not None:
                yield m
            else:
                try:
                    info.status.inc_loop_count()
                except LoopCountLimit:
                    break


class Reader(object):
    def __init__(self, filename, use_cache=True, **kwargs):
        self.filename = filename
        self.use_cache = use_cache


class AmmoFileReader(Reader):
    """Read missiles from ammo file"""

    def __init__(self, filename, use_cache=True, **kwargs):
        super(AmmoFileReader, self).__init__(filename, use_cache)
        self.log = logging.getLogger(__name__)
        self.log.info("Loading ammo from '%s'" % filename)

    @staticmethod
    def read_chunk_header(ammo_file):
        chunk_header = b''
        while chunk_header == b'':
            line = ammo_file.readline()
            if line == b'':
                return line
            chunk_header = line.strip(b'\r\n')
        return chunk_header

    def __iter__(self):
        opener = resource.get_opener(self.filename)
        with opener(self.use_cache) as ammo_file:
            info.status.af_size = opener.data_length
            chunk_header = self.read_chunk_header(ammo_file)
            while chunk_header:
                if chunk_header != b'':
                    try:
                        fields = chunk_header.split()
                        chunk_size = int(fields[0])
                        if chunk_size == 0:
                            if info.status.loop_count == 0:
                                self.log.info(
                                    'Zero-sized chunk in ammo file at %s. Starting over.'
                                    % ammo_file.tell())
                            ammo_file.seek(0)
                            try:
                                info.status.inc_loop_count()
                            except LoopCountLimit:
                                break
                            chunk_header = self.read_chunk_header(ammo_file)
                            continue
                        marker = fields[1] if len(fields) > 1 else None
                        missile = ammo_file.read(chunk_size)
                        if len(missile) < chunk_size:
                            raise AmmoFileError(
                                "Unexpected end of file: read %s bytes instead of %s"
                                % (len(missile), chunk_size))
                        yield (missile, marker)
                    except (IndexError, ValueError) as e:
                        raise AmmoFileError(
                            "Error while reading ammo file. Position: %s, header: '%s', original exception: %s"
                            % (ammo_file.tell(), chunk_header, e))
                chunk_header = self.read_chunk_header(ammo_file)
                if chunk_header == b'':
                    ammo_file.seek(0)
                    try:
                        info.status.inc_loop_count()
                    except LoopCountLimit:
                        break
                    chunk_header = self.read_chunk_header(ammo_file)
                info.status.af_position = ammo_file.tell()


class SlowLogReader(Reader):
    """Read missiles from SQL slow log. Not usable with Phantom"""
    def __iter__(self):
        opener = resource.get_opener(self.filename)
        with opener(self.use_cache) as ammo_file:
            info.status.af_size = opener.data_length
            request = ""
            while True:
                for line in ammo_file:
                    info.status.af_position = ammo_file.tell()
                    if isinstance(line, bytes):
                        line = line.decode('utf-8')
                    if line.startswith('#'):
                        if request != "":
                            yield (request, None)
                            request = ""
                    else:
                        request += line
                ammo_file.seek(0)
                info.status.af_position = 0
                try:
                    info.status.inc_loop_count()
                except LoopCountLimit:
                    break


class LineReader(Reader):
    """One line -- one missile"""

    def __iter__(self):
        opener = resource.get_opener(self.filename)
        with opener(self.use_cache) as ammo_file:
            info.status.af_size = opener.data_length
            while True:
                for line in ammo_file:
                    info.status.af_position = ammo_file.tell()
                    yield (line.rstrip(b'\r\n'), None) if isinstance(line, bytes) else (line.rstrip('\r\n').encode('utf8'), None)
                ammo_file.seek(0)
                info.status.af_position = 0
                try:
                    info.status.inc_loop_count()
                except LoopCountLimit:
                    break


class CaseLineReader(Reader):
    """One line -- one missile with case, tab separated"""

    def __iter__(self):
        opener = resource.get_opener(self.filename)
        with opener(self.use_cache) as ammo_file:
            info.status.af_size = opener.data_length
            while True:
                for line in ammo_file:
                    info.status.af_position = ammo_file.tell()
                    parts = line.rstrip(b'\r\n').split(b'\t', 1)
                    if len(parts) == 2:
                        yield (parts[1], parts[0])
                    elif len(parts) == 1:
                        yield (parts[0], None)
                    else:
                        raise RuntimeError("Unreachable branch")
                ammo_file.seek(0)
                info.status.af_position = 0
                try:
                    info.status.inc_loop_count()
                except LoopCountLimit:
                    break


class AccessLogReader(Reader):
    """Missiles from access log"""

    def __init__(self, filename, headers=None, http_ver='1.1', use_cache=True, **kwargs):
        super(AccessLogReader, self).__init__(filename, use_cache)
        self.warned = False
        self.headers = set(headers) if headers else set()
        self.log = logging.getLogger(__name__)

    def warn(self, message):
        if not self.warned:
            self.warned = True
            self.log.warning(
                "There are some skipped lines. See full log for details.")
        self.log.debug(message)

    def __iter__(self):
        opener = resource.get_opener(self.filename)
        with opener(self.use_cache) as ammo_file:
            info.status.af_size = opener.data_length
            while True:
                for line in ammo_file:
                    info.status.af_position = ammo_file.tell()
                    if isinstance(line, bytes):
                        line = line.decode('utf-8')
                    try:
                        request = line.split('"')[1]
                        method, uri, proto = request.split()
                        http_ver = proto.split('/')[1]
                        if method == "GET":
                            yield (
                                HttpAmmo(
                                    uri,
                                    headers=self.headers,
                                    http_ver=http_ver, ).to_s(), None)
                        else:
                            self.warn(
                                "Skipped line: %s (unsupported method)" % line)
                    except (ValueError, IndexError) as e:
                        self.warn("Skipped line: %s (%s)" % (line, e))
                ammo_file.seek(0)
                info.status.af_position = 0
                try:
                    info.status.inc_loop_count()
                except LoopCountLimit:
                    break


def _parse_header(header):
    return dict([(h.strip().decode('utf8') for h in header.split(b':', 1))])


class UriReader(Reader):
    def __init__(self, filename, headers=None, http_ver='1.1', use_cache=True, **kwargs):
        super(UriReader, self).__init__(filename, use_cache)
        self.headers = {pair[0].strip(): pair[1].strip() for pair in [h.split(':', 1) for h in headers]} \
            if headers else {}
        self.http_ver = http_ver
        self.log = logging.getLogger(__name__)
        self.log.info("Loading ammo from '%s' using URI format." % filename)

    def __iter__(self):
        opener = resource.get_opener(self.filename)
        with opener(self.use_cache) as ammo_file:
            info.status.af_size = opener.data_length
            while True:
                for line in ammo_file:
                    info.status.af_position = ammo_file.tell()
                    # if isinstance(line, bytes):
                    #     line = line.decode('utf-8')
                    if line.startswith(b'['):
                        self.headers.update(
                            _parse_header(line.strip(b'\r\n[]\t ')))
                    elif len(line.rstrip(b'\r\n')):
                        fields = line.split()
                        uri = fields[0]
                        if len(fields) > 1:
                            marker = fields[1]
                        else:
                            marker = None
                        yield (
                            HttpAmmo(
                                uri,
                                headers=[
                                    ': '.join(header)
                                    for header in self.headers.items()
                                ],
                                http_ver=self.http_ver, ).to_s(), marker)
                if info.status.ammo_count == 0:
                    self.log.error("No ammo in uri-style file")
                    raise AmmoFileError("No ammo! Cover me!")
                ammo_file.seek(0)
                info.status.af_position = 0
                try:
                    info.status.inc_loop_count()
                except LoopCountLimit:
                    break


class UriPostReader(Reader):
    """Read POST missiles from ammo file"""

    def __init__(self, filename, headers=None, http_ver='1.1', use_cache=True, **kwargs):
        super(UriPostReader, self).__init__(filename, use_cache)
        self.headers = {pair[0].strip(): pair[1].strip() for pair in [h.split(':', 1) for h in headers]} \
            if headers else {}
        self.http_ver = http_ver
        self.log = logging.getLogger(__name__)
        self.log.info("Loading ammo from '%s' using URI+POST format", filename)

    def __iter__(self):
        def read_chunk_header(ammo_file):
            chunk_header = b''
            while chunk_header == b'':
                line = ammo_file.readline()
                if line.startswith(b'['):
                    self.headers.update(_parse_header(line.strip(b'\r\n[]\t ')))
                elif line == b'':
                    return line
                else:
                    chunk_header = line.strip(b'\r\n')
            return chunk_header

        opener = resource.get_opener(self.filename)
        with opener(self.use_cache) as ammo_file:
            info.status.af_size = opener.data_length
            # if we got StopIteration here, the file is empty
            chunk_header = read_chunk_header(ammo_file)
            while chunk_header:
                if chunk_header != b'':
                    try:
                        fields = chunk_header.split()
                        chunk_size = int(fields[0])
                        uri = fields[1]
                        marker = fields[2] if len(fields) > 2 else None
                        if chunk_size == 0:
                            missile = b""
                        else:
                            missile = ammo_file.read(chunk_size)
                        if len(missile) < chunk_size:
                            raise AmmoFileError(
                                "Unexpected end of file: read %s bytes instead of %s"
                                % (len(missile), chunk_size))
                        yield (
                            HttpAmmo(
                                uri=uri,
                                headers=[
                                    ': '.join(header)
                                    for header in self.headers.items()
                                ],
                                method='POST',
                                body=missile,
                                http_ver=self.http_ver, ).to_s(), marker)
                    except (IndexError, ValueError) as e:
                        raise AmmoFileError(
                            "Error while reading ammo file. Position: %s, header: '%s', original exception: %s"
                            % (ammo_file.tell(), chunk_header, e))
                chunk_header = read_chunk_header(ammo_file)
                if chunk_header == b'':
                    self.log.debug(
                        'Reached the end of ammo file. Starting over.')
                    ammo_file.seek(0)
                    try:
                        info.status.inc_loop_count()
                    except LoopCountLimit:
                        break
                    chunk_header = read_chunk_header(ammo_file)
                info.status.af_position = ammo_file.tell()
