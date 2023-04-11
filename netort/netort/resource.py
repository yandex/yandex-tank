""" Resource Opener tool """
from __future__ import print_function

import logging
import os
import requests
import gzip
import hashlib
import serial
import yaml
import socket
import six
from netort.data_manager.common.util import thread_safe_property
from six.moves.urllib.parse import urlparse
from contextlib import closing

logger = logging.getLogger(__name__)

try:
    import boto
    import boto.s3.connection
except ImportError:
    logger.warning(
        'Failed to import `boto` package. Install `boto`, otherwise S3 file paths opener wont work',
        exc_info=False
    )
    boto = None

try:
    from library.python import resource as rs
    pip = False
except ImportError:
    pip = True


class FormatDetector(object):
    """ Format Detector
    """

    def __init__(self):
        self.formats = {'gzip': (0, b'\x1f\x8b'), 'tar': (257, b'ustar\x0000')}

    def detect_format(self, header):
        for fmt, signature in self.formats.items():
            if signature[1] == header[signature[0]:len(signature[1])]:
                return fmt


class ResourceManager(object):
    """ Resource opener manager.
        Use resource_filename and resource_string methods.
    """

    def __init__(self):
        self.path = None
        self.openers = {
            'http': ('http://', HttpOpener),
            'https': ('https://', HttpOpener),
            's3': ('s3://', S3Opener),
            'serial': ('/dev/', SerialOpener),
        }

    def resource_filename(self, path):
        """
        Args:
            path: str, resource file url or resource file absolute/relative path.

        Returns:
            string, resource absolute path (downloads the url to /tmp)
        """
        return self.get_opener(path).get_filename

    def resource_string(self, path):
        """
        Args:
            path: str, resource file url or resource file absolute/relative path.

        Returns:
            string, file content
        """
        opener = self.get_opener(path)
        filename = opener.get_filename
        try:
            size = os.path.getsize(filename)
            if size > 50 * 1024 * 1024:
                logger.warning(
                    'Reading large resource to memory: %s. Size: %s bytes',
                    filename, size)
        except Exception as exc:
            logger.debug('Unable to check resource size %s. %s', filename, exc)
        with opener(filename, 'r') as resource:
            content = resource.read()
        return content

    def get_opener(self, path):
        """
        Args:
            path: str, resource file url or resource file absolute/relative path.

        Returns:
            file object
        """
        self.path = rs.find(path) if not pip and path in rs.iterkeys(prefix='resfs/file/load/projects/yandex-tank/')\
            else path
        opener = None
        # FIXME this parser/matcher should use `urlparse` stdlib
        for opener_name, signature in self.openers.items():
            if self.path.startswith(signature[0]):
                opener = signature[1](self.path)
                break
        if not opener:
            opener = FileOpener(self.path)
        return opener


class SerialOpener(object):
    """ Serial device opener.
    """

    def __init__(self, device, baud_rate=230400, read_timeout=1):
        self.baud_rate = baud_rate
        self.device = device
        self.read_timeout = read_timeout

    def __call__(self, *args, **kwargs):
        return serial.Serial(self.device, self.baud_rate, timeout=self.read_timeout)

    @property
    def get_filename(self):
        return self.device


class FileOpener(object):
    """ File opener.
    """

    def __init__(self, f_path):
        self.f_path = f_path
        self.fmt_detector = FormatDetector()

    def __call__(self, *args, **kwargs):
        with open(self.f_path, 'rb') as resource:
            header = resource.read(300)
        fmt = self.fmt_detector.detect_format(header)
        logger.debug('Resource %s format detected: %s.', self.f_path, fmt)
        if fmt == 'gzip':
            return gzip.open(self.f_path, 'rb')
        else:
            return open(self.f_path, 'rb')

    @property
    def get_filename(self):
        return self.f_path

    @property
    def hash(self):
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


def retry(func):
    def with_retry(self, *args, **kwargs):
        for i in range(self.attempts):
            try:
                return func(self, *args, **kwargs)
            except Exception:
                logger.error('{} failed. Retrying.'.format(func), exc_info=True)
                continue
        return func(self, *args, **kwargs)
    return with_retry


class HttpOpener(object):
    """ Http url opener.
        Downloads small files.
        For large files returns wrapped http stream.
    """

    def __init__(self, url, timeout=5, attempts=5):
        self._filename = None
        self.url = url
        self.fmt_detector = FormatDetector()
        self.force_download = None
        self.data_info = None
        self.timeout = timeout
        self.attempts = attempts
        self.get_request_info()

    def __call__(self, use_cache=True, *args, **kwargs):
        return self.open(use_cache, *args, **kwargs)

    @retry
    def open(self, use_cache, *args, **kwargs):
        with closing(
                requests.get(
                    self.url, stream=True, verify=False,
                    timeout=self.timeout)) as stream:
            stream_iterator = stream.raw.stream(100, decode_content=True)
            header = next(stream_iterator)
            while len(header) < 10:
                header += next(stream_iterator)
            fmt = self.fmt_detector.detect_format(header)
            logger.debug('Resource %s format detected: %s.', self.url, fmt)
        if not self.force_download and fmt != 'gzip' and self.data_length > 10**8:
            logger.info(
                "Resource data is not gzipped and larger than 100MB. Reading from stream.."
            )
            return HttpBytesStreamWrapper(self.url)
        else:
            downloaded_f_path = self.download_file(use_cache)
            if fmt == 'gzip':
                return gzip.open(downloaded_f_path, mode='rb')
            else:
                return open(downloaded_f_path, 'rb')

    @retry
    def download_file(self, use_cache, try_ungzip=False):
        tmpfile_path = self.tmpfile_path()
        if os.path.exists(tmpfile_path) and use_cache:
            logger.info(
                "Resource %s has already been downloaded to %s . Using it..",
                self.url, tmpfile_path)
        else:
            logger.info("Downloading resource %s to %s", self.url, tmpfile_path)
            try:
                data = requests.get(self.url, verify=False, timeout=self.timeout)
            except requests.exceptions.Timeout:
                logger.info('Connection timeout reached trying to download resource via HttpOpener: %s',
                            self.url, exc_info=True)
                raise
            else:
                f = open(tmpfile_path, "wb")
                f.write(data.content)
                f.close()
                logger.info("Successfully downloaded resource %s to %s", self.url, tmpfile_path)
        if try_ungzip:
            try:
                if tmpfile_path.endswith('.gz'):
                    ungzippedfile_path = tmpfile_path[:-3]
                else:
                    ungzippedfile_path = tmpfile_path + '_ungzipped'
                with gzip.open(tmpfile_path) as gzf, open(ungzippedfile_path, 'wb') as f:
                    f.write(gzf.read())
                tmpfile_path = ungzippedfile_path
            except IOError as ioe:
                logger.error('Failed trying to unzip downloaded resource %s' % repr(ioe))
        self._filename = tmpfile_path
        return tmpfile_path

    def tmpfile_path(self):
        hasher = hashlib.md5()
        hasher.update(six.ensure_binary(self.hash))
        return "/tmp/http_%s.downloaded_resource" % hasher.hexdigest()

    @retry
    def get_request_info(self):
        logger.debug('Trying to get info about resource %s', self.url)
        req = requests.Request(
            'HEAD', self.url, headers={'Accept-Encoding': 'identity'})
        session = requests.Session()
        prepared = session.prepare_request(req)
        try:
            self.data_info = session.send(
                prepared,
                verify=False,
                allow_redirects=True,
                timeout=self.timeout)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            logger.warning('Connection error trying to get info for resource %s. Retrying...', self.url, exc_info=True)
            try:
                self.data_info = session.send(
                    prepared,
                    verify=False,
                    allow_redirects=True,
                    timeout=self.timeout)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                logger.warning(
                    'Connection error trying to get info for resource %s. Retrying...',
                    self.url, exc_info=True)
                raise
        finally:
            session.close()
        try:
            self.data_info.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            if exc.response.status_code == 405:
                logger.info(
                    "Resource storage does not support HEAD method. Ignore proto error and force download file."
                )
                self.force_download = True
            else:
                logger.warning('Invalid HTTP response trying to get info about resource: %s', self.url, exc_info=True)
                raise

    @thread_safe_property
    def get_filename(self):
        return self.download_file(use_cache=True)

    @property
    def hash(self):
        last_modified = self.data_info.headers.get("Last-Modified", '')
        hash = self.url + "|" + last_modified
        logger.info('Hash: {}'.format(hash))
        return self.url + "|" + last_modified

    @property
    def data_length(self):
        data_length = int(self.data_info.headers.get("Content-Length", 0))
        return data_length


class HttpBytesStreamWrapper:
    """
    makes http stream to look like file object
    """

    def __init__(self, url):
        self.next = self.__next__
        self.url = url
        self.buffer = b''
        self.pointer = 0
        self.stream_iterator = None
        self._content_consumed = False
        self.chunk_size = 10**3
        try:
            self.stream = requests.get(
                self.url, stream=True, verify=False, timeout=10)
            self.stream_iterator = self.stream.iter_content(self.chunk_size)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            logger.warning(
                'Connection errors or timeout reached trying to create HTTP stream for res: %s', self.url, exc_info=True
            )
            raise
        try:
            self.stream.raise_for_status()
        except requests.exceptions.HTTPError:
            logger.warning('Invalid HTTP response trying to open stream for resource: %s', self.url, exc_info=True)
            raise

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.stream.connection.close()

    def __iter__(self):
        return self

    def _reopen_stream(self):
        self.stream.connection.close()
        try:
            self.stream = requests.get(
                self.url, stream=True, verify=False, timeout=30)
            self.stream_iterator = self.stream.iter_content(self.chunk_size)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            logger.warning(
                'Connection errors or timeout reached trying to reopen stream while downloading resource: %s',
                self.url, exc_info=True
            )
            raise
        try:
            self.stream.raise_for_status()
        except requests.exceptions.HTTPError:
            logger.warning(
                'Invalid HTTP response trying to reopen stream for resource: %s',
                self.url, exc_info=True
            )
            raise
        self._content_consumed = False

    def _enhance_buffer(self):
        self.buffer += next(self.stream_iterator)

    def tell(self):
        return self.pointer

    def seek(self, position):
        if self.pointer:
            self.buffer = b''
            self._reopen_stream()
            self._enhance_buffer()
            while len(self.buffer) < position:
                self._enhance_buffer()
            self.pointer = position
            self.buffer = self.buffer[position:]

    def __next__(self):
        while b'\n' not in self.buffer:
            try:
                self._enhance_buffer()
            except (
                    StopIteration, TypeError,
                    requests.exceptions.StreamConsumedError):
                self._content_consumed = True
                break
        if not self._content_consumed or self.buffer:
            try:
                line = self.buffer[:self.buffer.index(b'\n') + 1]
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
            except (
                    StopIteration, TypeError,
                    requests.exceptions.StreamConsumedError):
                break
        if len(self.buffer) > chunk_size:
            chunk = self.buffer[:chunk_size]
        else:
            chunk = self.buffer
        self.pointer += len(chunk)
        self.buffer = self.buffer[len(chunk):]
        return chunk

    def readline(self):
        """
        requests iter_lines() uses splitlines() thus losing '\r\n'
        we need a different behavior for AmmoFileReader
        and we have to use our buffer because we have probably read
        a bunch into it already
        """
        try:
            return next(self)
        except StopIteration:
            return b''


class S3Opener(object):
    """ Simple Storage Service opener
        Downloads files.

        s3credentials.json fmt:
        {
            "aws_access_key_id": "key-id",
            "aws_secret_access_key": "secret-id",
            "host": "hostname.tld",
            "port": 7480,
            "is_secure": false
        }
    """

    def __init__(self, uri, credentials_path='/etc/yandex-tank/s3credentials.json'):
        # read s3 credentials
        # FIXME move to default config? which section and how securely store the keys?
        with open(credentials_path) as fname:
            s3_credentials = yaml.load(fname.read())
        self.host = s3_credentials.get('host')
        self.port = s3_credentials.get('port')
        self.is_secure = s3_credentials.get('is_secure', False)
        self.aws_access_key_id = s3_credentials.get('aws_access_key_id')
        self.aws_secret_access_key = s3_credentials.get('aws_secret_access_key')
        self.uri = uri
        urlparsed = urlparse(self.uri)
        self.bucket_key = urlparsed.netloc
        self.object_key = urlparsed.path.strip('/')
        self._filename = None
        self._conn = None

    @thread_safe_property
    def conn(self):
        if self._conn is None:
            if not boto:
                raise RuntimeError("Install 'boto' python package manually please")
            logger.debug('Opening connection to s3 %s:%s', self.host, self.port)
            self._conn = boto.connect_s3(
                host=self.host,
                port=self.port,
                is_secure=self.is_secure,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                calling_format=boto.s3.connection.OrdinaryCallingFormat(),
            )
        return self._conn

    def __call__(self, *args, **kwargs):
        return self.open(*args, **kwargs)

    def open(self):
        if not self._filename:
            self._filename = self.get_file()
        return open(self._filename, 'rb')

    @thread_safe_property
    def get_filename(self):
        return self.get_file()

    def tmpfile_path(self):
        hasher = hashlib.md5()
        hasher.update(self.hash)
        return "/tmp/s3_%s.downloaded_resource" % hasher.hexdigest()

    def get_file(self):
        if not self.conn:
            raise Exception('Connection should be initialized first')
        tmpfile_path = self.tmpfile_path()
        logger.info("Downloading resource %s to %s", self.uri, tmpfile_path)
        try:
            bucket = self.conn.get_bucket(self.bucket_key)
        except socket.gaierror:
            logger.warning('Failed to connect to s3 host %s:%s', self.host, self.port)
            raise
        except boto.exception.S3ResponseError:
            logger.warning('S3 error trying to get bucket: %s', self.bucket_key)
            logger.debug('S3 error trying to get bucket: %s', self.bucket_key, exc_info=True)
            raise
        except Exception:
            logger.debug('Failed to get s3 resource: %s', self.uri, exc_info=True)
            raise RuntimeError('Failed to get s3 resource %s' % self.uri)
        else:
            try:
                key = bucket.get_key(self.object_key)
                if not key:
                    raise RuntimeError('No such object %s at bucket %s', self.object_key, self.bucket_key)
                else:
                    key.get_contents_to_filename(tmpfile_path)
            except boto.exception.S3ResponseError:
                logger.warning(
                    'S3 error trying to get key %s from bucket: %s',
                    self.object_key, self.bucket_key
                )
                logger.debug(
                    'S3 error trying to get key %s from bucket: %s',
                    self.object_key, self.bucket_key, exc_info=True
                )
                raise
            else:
                logger.info("Successfully downloaded resource %s to %s", self.uri, tmpfile_path)
                self._filename = tmpfile_path
                return tmpfile_path

    @property
    def hash(self):
        hashed_str = "{bucket_key}_{object_key}".format(
            bucket_key=self.bucket_key,
            object_key=self.object_key,
        )
        return hashed_str

    @property
    def data_length(self):
        return os.path.getsize(self.get_filename)


manager = ResourceManager()
