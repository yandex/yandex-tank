'''
Utilities: parsers, converters, etc.
'''
import re
import logging
from itertools import islice
from module_exceptions import StepperConfigurationError
import math
import gzip
import requests
import os
import hashlib

logging.getLogger("requests").setLevel(logging.WARNING)


def take(number, iter):
    return list(islice(iter, 0, number))


def parse_duration(duration):
    '''
    Parse duration string, such as '3h2m3s' into milliseconds

    >>> parse_duration('3h2m3s')
    10923000

    >>> parse_duration('0.3s')
    300

    >>> parse_duration('5')
    5000
    '''
    _re_token = re.compile("([0-9.]+)([dhms]?)")

    def parse_token(time, multiplier):
        multipliers = {
            'h': 3600,
            'm': 60,
            's': 1,
        }
        if multiplier:
            if multiplier in multipliers:
                return int(float(time) * multipliers[multiplier] * 1000)
            else:
                raise StepperConfigurationError(
                    'Failed to parse duration: %s' % duration)
        else:
            return int(float(time) * 1000)

    return sum(parse_token(*token) for token in _re_token.findall(duration))


def solve_quadratic(a, b, c):
    '''
    >>> solve_quadratic(1.0, 2.0, 1.0)
    (-1.0, -1.0)
    '''
    discRoot = math.sqrt((b * b) - 4 * a * c)
    root1 = (-b - discRoot) / (2 * a)
    root2 = (-b + discRoot) / (2 * a)
    return (root1, root2)


def s_to_ms(f_sec):
    return int(f_sec * 1000.0)


def get_opener(f_path):
    """ Returns sub_opener function according to file extensions:
        both open and gzip.open calls return fileobj.

    Args:
        f_path: str, ammo file url.

    Returns:
        object, to call for file open.
    """
    if f_path.startswith("http://") or f_path.startswith("https://"):
        opener = HttpOpener(f_path)
    elif f_path.endswith('.gz'):
        opener = GZOpener(f_path)
    else:
        opener = FSOpener(f_path)
    return opener


class GZOpener(object):

    def __init__(self, f_path):
        self.f_path = f_path

    def __call__(self, *args, **kwargs):
        return gzip.open(*args, **kwargs)

    @property
    def hash(self):
        sep = "|"
        hashed_str = os.path.realpath(self.f_path)
        stat = os.stat(self.f_path)
        cnt = 0
        for stat_option in stat:
            if cnt == 7:  # skip access time
                continue
            cnt += 1
            hashed_str += ";" + str(stat_option)
        hashed_str += ";" + str(os.path.getmtime(self.f_path))
        return hashed_str

    @property
    def data_length(self):
        return os.path.getsize(self.f_path)


class FSOpener(object):

    def __init__(self, f_path):
        self.f_path = f_path

    def __call__(self, *args, **kwargs):
        return open(*args, **kwargs)

    @property
    def hash(self):
        sep = "|"
        hashed_str = os.path.realpath(self.f_path)
        stat = os.stat(self.f_path)
        cnt = 0
        for stat_option in stat:
            if cnt == 7:  # skip access time
                continue
            cnt += 1
            hashed_str += ";" + str(stat_option)
        hashed_str += ";" + str(os.path.getmtime(self.f_path))
        return hashed_str

    @property
    def data_length(self):
        return os.path.getsize(self.f_path)


class HttpOpener(object):

    '''
    downloads small files
    for large files returns wrapped http stream
    '''

    def __init__(self, url):
        self.url = url
        # Meta params
        self.gzip = False
        self.data_info = requests.head(self.url, verify=False, allow_redirects=True, headers={'Accept-Encoding': 'identity'})

    def __call__(self, *args, **kwargs):
        return self.open(*args, **kwargs)

    def open(self, *args, **kwargs):
        if self.data_info.status_code == 200:
            self._detect_gzip()
            if not self.gzip and self.data_length > 10 ** 8:
                logging.info(
                    "Ammofile data is larger than 100MB. Reading from stream..")
                return HttpStreamWrapper(self.url)
            else:
                hasher = hashlib.md5()
                hasher.update(self.hash)
                tmpfile_path = "/tmp/%s" % hasher.hexdigest()
                if os.path.exists(tmpfile_path):
                    logging.info(
                        "Ammofile has already been downloaded to %s . Using it..", tmpfile_path)
                else:
                    logging.info("Downloading ammofile to %s", tmpfile_path)
                    data = requests.get(self.url, verify=False)
                    f = open(tmpfile_path, "wb")
                    f.write(data.content)
                    f.close()
                if self.gzip:
                    return gzip.open(tmpfile_path, mode='rb')
                else:
                    return open(tmpfile_path, 'rb')
        elif self.data_info.status_code == 405:
            logging.info(
                "Ammo storage does not support HEAD method. Will have to download file")
            hasher = hashlib.md5()
            hasher.update(self.hash)
            tmpfile_path = "/tmp/%s" % hasher.hexdigest()
            if os.path.exists(tmpfile_path):
                logging.info(
                        "Ammofile has already been downloaded to %s . Using it..", tmpfile_path)
            else:
                logging.info("Downloading ammofile to %s", tmpfile_path)
                data = requests.get(self.url, verify=False)
                f = open(tmpfile_path, "wb")
                f.write(data.content)
                f.close()
            with open(tmpfile_path, mode='rb') as f:
                if f.read(2) == b'\037\213':
                    self.gzip = True
            if self.gzip:
                return gzip.open(tmpfile_path, mode='rb')
            else:
                return open(tmpfile_path, 'rb')
        else:
            raise RuntimeError(
                "Ammo file not found: %s %s" % (self.data_info.status_code, self.url))

    def _detect_gzip(self):
        stream = requests.get(self.url, stream=True, verify=False)
        if stream.status_code == 200:
            try:
                stream_iterator = stream.raw.stream(100, decode_content=True)
                gz_header = stream_iterator.next()
                if gz_header[:2] == b'\037\213':
                    logging.info("Ammofile data is in gz format")
                    self.gzip = True
            except:
                logging.exception("")
            finally:
                stream.connection.close()

    @property
    def hash(self):
        last_modified = self.data_info.headers.get("Last-Modified", '')
        return self.url + "|" + last_modified

    @property
    def data_length(self):
        try:
            data_length = int(self.data_info.headers.get("Content-Length", 0))
        except:
            data_length = 0
        return data_length


class HttpStreamWrapper():

    '''
    makes http stream to look like file object
    '''

    def __init__(self, url):
        self.url = url
        self.buffer = ''
        self.pointer = 0
        self.stream = requests.get(self.url, stream=True, verify=False)
        self._content_consumed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.connection.close()

    def __iter__(self):
        while True:
            yield self.next()

    def _reopen_stream(self):
        self.stream.connection.close()
        self.stream = requests.get(self.url, stream=True, verify=False)
        self._content_consumed = False

    def _enhance_buffer(self, bytes=10 ** 3):
        self.buffer += self.stream.iter_content(bytes).next()

    def tell(self):
        return self.pointer

    def seek(self, position):
        if self.pointer:
            self.buffer = ''
            self._reopen_stream()
            self._enhance_buffer()
            while len(self.buffer) < position:
                self._enhance_buffer()
            self.pointer = position
            self.buffer = self.buffer[position:]

    def next(self):
        while not '\n' in self.buffer:
            try:
                self._enhance_buffer()
            except (StopIteration, TypeError, requests.exceptions.StreamConsumedError):
                self._content_consumed = True
                break
        if not self._content_consumed or self.buffer:
            try:
                line = self.buffer[:self.buffer.index('\n') + 1]
            except ValueError:
                line = self.buffer
            self.pointer += len(line)
            self.buffer = self.buffer[len(line):]
            return line
        raise StopIteration

    def read(self, chunk_size):
        while len(self.buffer) < chunk_size:
            try:
                self._enhance_buffer()
            except (StopIteration, TypeError, requests.exceptions.StreamConsumedError):
                break
        if len(self.buffer) > chunk_size:
            chunk = self.buffer[:chunk_size]
        else:
            chunk = self.buffer
        self.pointer += len(chunk)
        self.buffer = self.buffer[len(chunk):]
        return chunk

    def readline(self):
        '''
        requests iter_lines() uses splitlines() thus losing '\r\n'
        we need a different behavior for AmmoFileReader
        and we have to use our buffer because we have probably read a bunch into it already
        '''
        try:
            return self.next()
        except StopIteration:
            return ''
