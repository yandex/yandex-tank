""" Resource Opener tool """
import logging
import os
import requests
import gzip
import hashlib
from contextlib import closing


class FormatDetector(object):
    """ Format Detector
    """
    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.formats = {
            'gzip': (0, b'\x1f\x8b'),
            'tar': (257, b'ustar\x0000')
        }

    def detect_format(self, header):
        for fmt, signature in self.formats.iteritems():
            if signature[1] == header[signature[0]:len(signature[1])]:
                return fmt


class Opener(object):
    """ Resource opener manager.
        Returns opener function according to file extensions.
        both open and gzip.open calls return fileobj.
    """

    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.path = None

    def get_opener(self, path):
        """
        Args:
            path: str, ammo file url or ammo file absolute/relative path.

        Returns:
            object, to call for file open.
        """
        self.path = path
        if self.path.startswith("http://") or self.path.startswith("https://"):
            self.log.debug('Using HttpOpener for resource: %s', self.path)
            opener = HttpOpener(self.path)
        else:
            self.log.debug('Using FileOpener for resource: %s', self.path)
            opener = FileOpener(self.path)
        return opener


class FileOpener(object):
    """ File opener.
    """
    def __init__(self, f_path):
        self.log = logging.getLogger(__name__)
        self.f_path = f_path
        self.fmt_detector = FormatDetector()

    def __call__(self, *args, **kwargs):
        with open(self.f_path, 'rb') as resource:
            header = resource.read(300)
        fmt = self.fmt_detector.detect_format(header)
        self.log.debug('Resource %s format detected: %s.', self.f_path, fmt)
        if fmt == 'gzip':
            return gzip.open(*args, **kwargs)
        else:
            return open(*args, **kwargs)

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


class HttpOpener(object):
    """ Http url opener.
        Downloads small files.
        For large files returns wrapped http stream.
    """

    def __init__(self, url):
        self.log = logging.getLogger(__name__)
        self.url = url
        self.fmt_detector = FormatDetector()
        self.force_download = None
        self.data_info = None
        try:
            self.data_info = requests.head(
                self.url,
                verify=False,
                allow_redirects=True,
                headers={'Accept-Encoding': 'identity'},
                timeout=10
            )
            self.data_info.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(
                'Connection timeout reached '
                'trying to get info about resource: %s \n'
                'via HttpOpener: %s' % (self.url, exc)
            )
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                'Connection error '
                'trying to get info about resource: %s \n'
                'via HttpOpener: %s' % (self.url, exc)
            )
        except requests.exceptions.HTTPError as exc:
            if exc.response.status_code == 405:
                self.log.info(
                    "Resource storage does not support HEAD method. Ignore proto error and force download file.")
                self.force_download = True
            else:
                raise RuntimeError(
                    'Invalid HTTP response '
                    'trying to get info about resource: %s \n'
                    'via HttpOpener: %s' % (self.url, exc)
                )

    def __call__(self, *args, **kwargs):
        return self.open(*args, **kwargs)

    def open(self, *args, **kwargs):
        try:
            with closing(requests.get(self.url, stream=True, verify=False, timeout=10)) as stream:
                stream_iterator = stream.raw.stream(100, decode_content=True)
                header = stream_iterator.next()
                fmt = self.fmt_detector.detect_format(header)
                self.log.debug('Resource %s format detected: %s.', self.url, fmt)
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(
                'Connection timeout reached '
                'trying to get gzip info about resource: %s \n'
                'via HttpOpener: %s' % (self.url, exc)
            )

        if not self.force_download and fmt != 'gzip' and self.data_length > 10 ** 8:
            self.log.info(
                "Resource data is larger than 100MB. Reading from stream.."
            )
            return HttpStreamWrapper(self.url)
        else:
            downloaded_f_path = self.download_file()
            if fmt == 'gzip':
                return gzip.open(downloaded_f_path, mode='rb')
            else:
                return open(downloaded_f_path, 'rb')

    def download_file(self):
        hasher = hashlib.md5()
        hasher.update(self.hash)
        tmpfile_path = "/tmp/%s" % hasher.hexdigest()
        if os.path.exists(tmpfile_path):
            self.log.info(
                    "Resource %s has already been downloaded to %s . Using it..", self.url, tmpfile_path
            )
        else:
            self.log.info("Downloading resource %s to %s", self.url, tmpfile_path)
            try:
                data = requests.get(self.url, verify=False, timeout=10)
            except requests.exceptions.Timeout as exc:
                raise RuntimeError(
                    'Connection timeout reached '
                    'trying to download resource: %s \n'
                    'via HttpOpener: %s' % (self.url, exc)
                )
            f = open(tmpfile_path, "wb")
            f.write(data.content)
            f.close()
            self.log.info("Successfully downloaded resource %s to %s", self.url, tmpfile_path)
        return tmpfile_path

    @property
    def hash(self):
        last_modified = self.data_info.headers.get("Last-Modified", '')
        return self.url + "|" + last_modified

    @property
    def data_length(self):
        try:
            data_length = int(self.data_info.headers.get("Content-Length", 0))
        except:  # FIXME: this exception will catch everything.
            data_length = 0
        return data_length


class HttpStreamWrapper:
    """
    makes http stream to look like file object
    """

    def __init__(self, url):
        self.url = url
        self.buffer = ''
        self.pointer = 0
        self._content_consumed = False
        try:
            self.stream = requests.get(self.url, stream=True, verify=False, timeout=10)
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(
                'Connection timeout reached '
                'trying to make stream while downloading resource: %s \n'
                'via HttpOpener: %s' % (self.url, exc)
            )

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.stream.connection.close()

    def __iter__(self):
        while True:
            yield self.next()

    def _reopen_stream(self):
        self.stream.connection.close()
        try:
            self.stream = requests.get(self.url, stream=True, verify=False, timeout=30)
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(
                'Connection timeout reached '
                'trying to reopen stream while downloading resource: %s \n'
                'via HttpOpener: %s' % (self.url, exc)
            )
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
        while '\n' not in self.buffer:
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