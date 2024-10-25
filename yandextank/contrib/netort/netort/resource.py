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
import typing
import environ
from yandextank.contrib.netort.netort.data_manager.common.util import thread_safe_property, YamlEnvSubstConfigLoader
from yandextank.contrib.netort.netort.data_manager.common.condition import uri_like, path_like, Condition
from urllib.parse import urlparse
from contextlib import closing
from dataclasses import dataclass
from functools import partial

logger = logging.getLogger(__name__)

try:
    import boto3
    import boto3.exceptions
    import boto3.s3
    import boto3.session
except ImportError:
    logger.debug('Failed to import `boto3` package. Install `boto3`, otherwise S3 file paths opener wont work')
    boto3 = None

try:
    from library.python import resource as rs
    pip = False
except ImportError:
    pip = True

_TMP_PATH_PREFIX = os.getenv('NETORT_TMP_PATH', '/tmp')


class PathProvider(object):
    def __init__(self, prefix) -> None:
        self.prefix = prefix

    def tmpfile_path(self, hash):
        hasher = hashlib.md5()
        hasher.update(six.ensure_binary(hash))
        return '%s_%s.downloaded_resource' % (self.prefix, hasher.hexdigest())


class FormatDetector(object):
    """ Format Detector
    """

    def __init__(self):
        self.formats = {'gzip': (0, b'\x1f\x8b'), 'tar': (257, b'ustar\x0000')}

    def detect_format(self, header):
        for fmt, signature in self.formats.items():
            if signature[1] == header[signature[0]:len(signature[1])]:
                return fmt


@typing.runtime_checkable
class OpenerProtocol(typing.Protocol):
    def open(self) -> object: ...

    @property
    def filename(self) -> str: ...


@typing.runtime_checkable
class TempDownloaderOpenerProtocol(typing.Protocol):
    def open(self, use_cache: bool) -> object: ...

    def download_file(self, use_cache: bool, try_ungzip: bool) -> str: ...

    @thread_safe_property
    def filename(self) -> str: ...


@dataclass
class OpenerItem(object):
    condition: Condition
    factory: typing.Callable[[str], OpenerProtocol | TempDownloaderOpenerProtocol]
    order: int = 0


OpenersConfig = typing.Collection[OpenerItem]


@environ.config(prefix='NETORT')
class ResourceManagerConfig(object):
    tmp_path = environ.var('/tmp')
    openers_config_path = environ.var('/etc/yandex-tank/netort_openers.config')
    s3_endpoint_url = environ.var('')
    aws_access_key_id = environ.var('')
    aws_secret_access_key = environ.var('')


class ResourceManager(object):
    """ Resource opener manager.
        Use resource_filename and resource_string methods.
    """

    def __init__(
        self,
        config: ResourceManagerConfig,
        openers: OpenersConfig | None = None,
    ):
        self.config = config
        logger.debug('loading ResourceManager config from %s', config.openers_config_path)
        self.openers_config = self.make_openers_config(config, self.load_config_safe(config.openers_config_path))

        self.tmp_path_prefix = config.tmp_path
        self.openers = openers or self._default_openers()

    def make_path_provider(self, subfolder: str) -> PathProvider:
        return PathProvider(os.path.join(self.tmp_path_prefix, subfolder))

    def _default_openers(self) -> OpenersConfig:
        http_opener = partial(HttpOpener, config=self.openers_config.get('http_opener'), path_provider=self.make_path_provider('http'))
        s3_opener = partial(S3Opener, config=self.openers_config.get('s3_opener'), path_provider=self.make_path_provider('s3'))

        return [
            OpenerItem(uri_like(scheme='http'), http_opener),
            OpenerItem(uri_like(scheme='https'), http_opener),
            OpenerItem(uri_like(scheme='s3'), s3_opener),
            OpenerItem(uri_like(scheme='file'), FileOpener),
            OpenerItem(path_like('/dev/'), SerialOpener),
        ]

    def make_openers_config(
        self,
        rm_config: ResourceManagerConfig,
        openers_config: dict[str, typing.Any] | None,
    ) -> dict[str, typing.Any]:
        openers_config = openers_config or {}
        if rm_config.aws_access_key_id and rm_config.aws_secret_access_key and rm_config.s3_endpoint_url:
            openers_config['s3_opener'] = {
                'aws_access_key_id': rm_config.aws_access_key_id,
                'aws_secret_access_key': rm_config.aws_secret_access_key,
                'endpoint_url': rm_config.s3_endpoint_url,
            }
        return openers_config

    def load_config_safe(self, path) -> dict[str, typing.Any] | None:
        if not path:
            return None
        if not os.path.exists(path):
            logger.info('Netort ResourceManager config file %s not exists.', path)
            return None
        try:
            with open(path, 'r') as f:
                return yaml.load(f, Loader=YamlEnvSubstConfigLoader)
        except Exception as e:
            logger.warning('Failed to load openers config file at %s: %s', path, str(e))
            return None

    def resource_filename(self, path):
        """
        Args:
            path: str, resource file url or resource file absolute/relative path.

        Returns:
            string, resource absolute path (downloads the url to /tmp)
        """
        return self.get_opener(path).filename

    def resource_string(self, path):
        """
        Args:
            path: str, resource file url or resource file absolute/relative path.

        Returns:
            string, file content
        """
        opener = self.get_opener(path)
        filename = opener.filename
        try:
            size = os.path.getsize(filename)
            if size > 50 * 1024 * 1024:
                logger.warning('Reading large resource to memory: %s. Size: %s bytes', filename, size)
        except Exception as exc:
            logger.debug('Unable to check resource size %s. %s', filename, exc)
        with open_file(opener, use_cache=True) as resource:
            content = resource.read()
        return content

    def get_opener(self, path) -> OpenerProtocol | TempDownloaderOpenerProtocol:
        """
        Args:
            path: str, resource file url or resource file absolute/relative path.

        Returns:
            file object
        """
        path = rs.find(path) if not pip and path in rs.iterkeys(prefix='resfs/file/load/projects/yandex-tank/')\
            else path

        self._ensure_tmp_path_prefix_exists()
        openers = [o for o in self.openers if o.condition(path)]
        if not openers:
            return FileOpener(path)
        if len(openers) == 1:
            return openers[0].factory(path)

        explanation = '\n'.join([repr(o.condition) for o in openers])
        logger.info(f'multiple openers meets "{path}": {explanation}')
        opener = sorted(openers, key=lambda o: o.order, reverse=True)[0]
        logger.info(f'highest priority: {repr(opener.condition)}')
        return opener.factory(path)

    def _ensure_tmp_path_prefix_exists(self):
        if not os.path.exists(self.tmp_path_prefix):
            os.makedirs(self.tmp_path_prefix, exist_ok=True)


class SerialOpener(OpenerProtocol):
    """ Serial device opener.
    """

    def __init__(self, device, baud_rate=230400, read_timeout=1):
        self.baud_rate = baud_rate
        self.device = device
        self.read_timeout = read_timeout

    def open(self):
        return serial.Serial(self.device, self.baud_rate, timeout=self.read_timeout)

    @property
    def filename(self):
        return self.device


class FileOpener(OpenerProtocol):
    """ File opener.
    """

    def __init__(self, f_path):
        self.f_path = f_path
        self.fmt_detector = FormatDetector()

    def open(self):
        with open(self.f_path, 'rb') as resource:
            header = resource.read(300)
        fmt = self.fmt_detector.detect_format(header)
        logger.debug('Resource %s format detected: %s.', self.f_path, fmt)
        if fmt == 'gzip':
            return gzip.open(self.f_path, 'rb')
        else:
            return open(self.f_path, 'rb')

    @property
    def filename(self):
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
                logger.exception('%s failed. Retrying.', func)
                continue
        return func(self, *args, **kwargs)
    return with_retry


class HttpOpener(TempDownloaderOpenerProtocol):
    """ Http url opener.
        Downloads small files.
        For large files returns wrapped http stream.
    """

    def __init__(self, url, timeout=5, attempts=5, path_provider=None, config=None):
        self._filename = None
        self.url = url
        self.fmt_detector = FormatDetector()
        self.force_download = None
        self.data_info = None
        self.timeout = timeout
        self.attempts = attempts
        self.path_provider = path_provider or PathProvider(os.path.join(_TMP_PATH_PREFIX, 'http'))
        self._default_headers = None or self._parse_headers_from_config(config)
        self.get_request_info()

    def _parse_headers_from_config(self, config: dict[str, typing.Any] | None):
        if not config:
            return None
        parsed = urlparse(self.url)
        host = parsed.netloc.rsplit(':')[0]
        return config.get(host, {}).get('headers')

    @retry
    def open(self, use_cache=True):
        with closing(
                requests.get(
                    self.url, stream=True, verify=False, headers=self._default_headers,
                    timeout=self.timeout)) as stream:
            stream_iterator = stream.raw.stream(100, decode_content=True)
            header = next(stream_iterator)
            while len(header) < 10:
                header += next(stream_iterator)
            fmt = self.fmt_detector.detect_format(header)
            logger.debug('Resource %s format detected: %s.', self.url, fmt)

        if not self.force_download and fmt != 'gzip' and self.data_length > 10**8:
            logger.info("Resource data is not gzipped and larger than 100MB. Reading from stream..")
            return HttpBytesStreamWrapper(self.url, headers=self._default_headers)
        else:
            downloaded_f_path = self.download_file(use_cache)
            if fmt == 'gzip':
                return gzip.open(downloaded_f_path, mode='rb')
            else:
                return open(downloaded_f_path, 'rb')

    @retry
    def download_file(self, use_cache, try_ungzip=False) -> str:
        tmpfile_path = self.tmpfile_path()
        if os.path.exists(tmpfile_path) and use_cache:
            logger.info("Resource %s has already been downloaded to %s . Using it..", self.url, tmpfile_path)
        else:
            logger.info("Downloading resource %s to %s", self.url, tmpfile_path)
            try:
                data = requests.get(self.url, verify=False, headers=self._default_headers, timeout=self.timeout)
                data.raise_for_status()
            except requests.exceptions.Timeout:
                logger.info('Connection timeout reached trying to download resource via HttpOpener: %s',
                            self.url, exc_info=True)
                raise
            except requests.exceptions.HTTPError:
                logger.error('Bad http code during resource downloading. Http code: %s, resource: %s', data.status_code, self.url)
                raise
            else:
                f = open(tmpfile_path, "wb")
                f.write(data.content)
                f.close()
                logger.info("Successfully downloaded resource %s to %s, http status code: %s", self.url, tmpfile_path, data.status_code)
        if try_ungzip:
            tmpfile_path = try_ungzip_file(tmpfile_path)
        self._filename = tmpfile_path
        return tmpfile_path

    def tmpfile_path(self):
        return self.path_provider.tmpfile_path(self.hash)

    @retry
    def get_request_info(self):
        logger.debug('Trying to get info about resource %s', self.url)
        headers = self._default_headers or {}
        headers.update({'Accept-Encoding': 'identity'})
        req = requests.Request('HEAD', self.url, headers=headers)
        session = requests.Session()
        prepared = session.prepare_request(req)
        try:
            self.data_info = session.send(
                prepared,
                verify=False,
                allow_redirects=True,
                timeout=self.timeout,
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            logger.warning('Connection error trying to get info for resource %s. Retrying...', self.url, exc_info=True)
            try:
                self.data_info = session.send(
                    prepared,
                    verify=False,
                    allow_redirects=True,
                    timeout=self.timeout,
                )
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                logger.warning(
                    'Connection error trying to get info for resource %s. Retrying...',
                    self.url, exc_info=True,
                )
                raise
        finally:
            session.close()
        try:
            self.data_info.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            if exc.response.status_code == 405:
                logger.info(
                    "Resource storage does not support HEAD method. Ignore proto error and force download file.",
                )
                self.force_download = True
            else:
                logger.warning('Invalid HTTP response trying to get info about resource: %s', self.url, exc_info=True)
                raise

    @thread_safe_property
    def filename(self):
        if self._filename is None:
            self._filename = self.download_file(use_cache=True)
        return self._filename

    @property
    def hash(self):
        last_modified = self.data_info.headers.get("Last-Modified", '')
        hashed_str = self.url + "|" + last_modified
        logger.info('Hash: {}'.format(hashed_str))
        return hashed_str

    @property
    def data_length(self):
        data_length = int(self.data_info.headers.get("Content-Length", 0))
        return data_length


class HttpBytesStreamWrapper:
    """
    makes http stream to look like file object
    """

    def __init__(self, url, headers=None):
        self.next = self.__next__
        self.url = url
        self.headers = headers
        self.buffer = b''
        self.pointer = 0
        self.stream_iterator = None
        self._content_consumed = False
        self.chunk_size = 10**3
        try:
            self.stream = requests.get(
                self.url, stream=True, verify=False, timeout=10, headers=headers)
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
                self.url, stream=True, verify=False, timeout=30, headers=self.headers)
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


class S3Opener(TempDownloaderOpenerProtocol):
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

    def __init__(self, uri, credentials_path='/etc/yandex-tank/s3credentials.json', path_provider=None, config=None, attempts=5):
        s3_credentials = config
        if not s3_credentials:
            with open(credentials_path) as fname:
                s3_credentials = yaml.safe_load(fname.read())
        self.endpoint_url = s3_credentials.get('endpoint_url')
        self.aws_access_key_id = s3_credentials.get('aws_access_key_id')
        self.aws_secret_access_key = s3_credentials.get('aws_secret_access_key')
        self.uri = uri
        urlparsed = urlparse(self.uri)
        self.bucket_key = urlparsed.netloc
        self.object_key = urlparsed.path.strip('/')
        self.path_provider = path_provider or PathProvider(os.path.join(_TMP_PATH_PREFIX, 's3'))
        self._filename = None
        self._conn = None
        self.attempts = attempts

    @thread_safe_property
    def conn(self):
        if self._conn is None:
            if not boto3:
                raise RuntimeError("Install 'boto3' python package manually please")
            logger.debug('Opening connection to s3 %s', self.endpoint_url)
            session = boto3.session.Session()
            self._conn = session.client(
                service_name='s3',
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
            )
        return self._conn

    def open(self, use_cache=True):
        if not self._filename:
            self._filename = self.download_file(use_cache, try_ungzip=False)
        return open(self._filename, 'rb')

    def tmpfile_path(self):
        return self.path_provider.tmpfile_path(self.hash)

    @retry
    def download_file(self, use_cache, try_ungzip=False):
        tmpfile_path = self.tmpfile_path()
        if os.path.exists(tmpfile_path) and use_cache:
            logger.info("Resource %s has already been downloaded to %s . Using it..", self.uri, tmpfile_path)
        else:
            if not self.conn:
                raise Exception('Connection should be initialized first')
            logger.info("Downloading resource %s to %s", self.uri, tmpfile_path)

            try:
                self.conn.download_file(self.bucket_key, self.object_key, tmpfile_path)
            except socket.gaierror:
                logger.error('Failed to connect to s3 host %s', self.endpoint_url)
                raise
            except boto3.exceptions.Boto3Error as e:
                logger.error('S3 error trying to download file from bucket: %s/%s  %s', self.bucket_key,
                             self.object_key, str(e))
                logger.debug('S3 error trying to download file from bucket: %s/%s', self.bucket_key, self.object_key,
                             exc_info=True)
                raise
            except Exception as e:
                logger.debug('Failed to get s3 resource: %s', self.uri, exc_info=True)
                raise RuntimeError('Failed to get s3 resource %s' % self.uri) from e

            logger.info("Successfully downloaded resource %s to %s", self.uri, tmpfile_path)

        if try_ungzip:
            tmpfile_path = try_ungzip_file(tmpfile_path)
        self._filename = tmpfile_path
        return tmpfile_path

    @thread_safe_property
    def filename(self) -> str:
        if self._filename is None:
            self._filename = self.download_file(use_cache=True)
        return self._filename

    @property
    def hash(self):
        hashed_str = "{bucket_key}_{object_key}".format(
            bucket_key=self.bucket_key,
            object_key=self.object_key,
        )
        return hashed_str

    @property
    def data_length(self):
        return os.path.getsize(self.filename)


def make_resource_manager():
    return ResourceManager(environ.to_config(ResourceManagerConfig))


manager = make_resource_manager()


def try_ungzip_file(file_path: str) -> str:
    try:
        if file_path.endswith('.gz'):
            ungzippedfile_path = file_path[:-3]
        else:
            ungzippedfile_path = file_path + '_ungzipped'
        with gzip.open(file_path) as gzf, open(ungzippedfile_path, 'wb') as f:
            f.write(gzf.read())
        return ungzippedfile_path
    except IOError as ioe:
        logger.info('Failed trying to ungzip downloaded resource %s' % repr(ioe))
    return file_path


def open_file(opener: OpenerProtocol | TempDownloaderOpenerProtocol, use_cache: bool) -> object:
    if isinstance(opener, TempDownloaderOpenerProtocol):
        return opener.open(use_cache)
    return opener.open()
