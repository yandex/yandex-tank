'''
Ammo formatters
'''
import logging

from .module_exceptions import StpdFileError


class Stpd(object):
    '''
    STPD ammo formatter
    '''

    def __init__(self, ammo_factory):
        self.af = ammo_factory

    def __iter__(self):
        return (
            "%s %s %s\n%s\n" % (len(missile), timestamp, marker, missile)
            for timestamp, marker, missile in self.af)


class StpdReader(object):
    '''Read missiles from stpd file'''

    def __init__(self, filename):
        self.filename = filename
        self.log = logging.getLogger(__name__)
        self.log.info("Loading stepped missiles from '%s'" % filename)

    def __iter__(self):
        def read_chunk_header(ammo_file):
            chunk_header = ''
            while not chunk_header:
                line = ammo_file.readline().decode('utf8')
                if not line:
                    return line  # EOF
                chunk_header = line.strip('\r\n')
            return chunk_header

        with open(self.filename, 'rb') as ammo_file:
            chunk_header = read_chunk_header(ammo_file)
            while chunk_header != '':
                try:
                    fields = chunk_header.split()
                    chunk_size = int(fields[0])
                    timestamp = int(fields[1])
                    marker = fields[2] if len(fields) > 2 else ''
                    missile = ammo_file.read(chunk_size)
                    if len(missile) < chunk_size:
                        raise StpdFileError(
                            "Unexpected end of file: read %s bytes instead of %s"
                            % (len(missile), chunk_size))
                    yield (timestamp, missile, marker)
                except (IndexError, ValueError) as e:
                    raise StpdFileError(
                        "Error while reading ammo file. Position: %s, header: '%s', original exception: %s"
                        % (ammo_file.tell(), chunk_header, e))
                chunk_header = read_chunk_header(ammo_file)
        self.log.info("Reached the end of stpd file")
