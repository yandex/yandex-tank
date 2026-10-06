import logging
import os
import re
import time
from threading import Event, Thread

MAX_EVENT_LINES = 1000
MAX_EVENT_MESSAGE_BYTES = 2000
MAX_STOP_TAIL_BYTES = 64 * 1024

_LEVEL_PREFIX_RE = re.compile(
    r'^(?:\d{4}[-/]\d{2}[-/]\d{2}(?:[T ]\S+)?\s+)?' r'\[?(DEBUG|INFO|WARN(?:ING)?|ERROR|FATAL|PANIC|DPANIC)\]?(?=\s|$)',
    re.IGNORECASE,
)


class PandoraOutputReader:
    """Copy bounded Pandora process output from its artifact into the event logger."""

    def __init__(self, path, process, logger: logging.Logger, max_lines: int = MAX_EVENT_LINES):
        self._path = path
        self._process = process
        self._logger = logger
        self._max_lines = max_lines
        self._extra = {'source': 'pandora'}
        self._stop = Event()
        self._thread = Thread(target=self._run, name='pandora-output-events', daemon=True)
        self._debug_limit = max_lines // 10 if max_lines >= 10 else 0
        self._regular_limit = max_lines - 2 if max_lines >= 10 else max_lines
        self._regular_sent = 0
        self._debug_sent = 0
        self._last_error = None
        self._last_fatal = None
        self._dropped = 0
        self._unscanned_bytes = 0
        self._stop_limit = None
        self._stop_deadline = None
        self.consumed_offset = 0
        self.stop_timed_out = False
        self.failed = False

    def start(self):
        self._thread.start()

    def stop(self):
        if self._stop.is_set():
            return
        try:
            self._stop_limit = os.path.getsize(self._path)
        except OSError:
            self._stop_limit = 0
        self._stop_deadline = time.monotonic() + 0.4
        self._stop.set()
        self._thread.join(timeout=0.6)
        if self._thread.is_alive():
            self.stop_timed_out = True

    @staticmethod
    def _level(line: str) -> int:
        line = line.lstrip()
        if line.lower().startswith('panic:'):
            return logging.CRITICAL
        match = _LEVEL_PREFIX_RE.match(line)
        if match is None:
            return logging.INFO
        level = match.group(1).upper()
        if level in ('FATAL', 'PANIC', 'DPANIC'):
            return logging.CRITICAL
        if level == 'ERROR':
            return logging.ERROR
        if level in ('WARN', 'WARNING'):
            return logging.WARNING
        if level == 'DEBUG':
            return logging.DEBUG
        return logging.INFO

    def _emit(self, line: bytes):
        if not line:
            return
        message = line[:MAX_EVENT_MESSAGE_BYTES].decode('utf-8', errors='replace').rstrip('\r')
        level = self._level(message)
        if not self._logger.isEnabledFor(level):
            return
        if level < logging.INFO:
            if self._debug_sent < self._debug_limit and self._regular_sent < self._regular_limit:
                self._debug_sent += 1
                self._regular_sent += 1
                self._logger.log(level, message, extra=self._extra)
            else:
                self._dropped += 1
            return
        if self._regular_sent < self._regular_limit:
            self._regular_sent += 1
            self._logger.log(level, message, extra=self._extra)
            return
        if self._max_lines >= 10 and level >= logging.CRITICAL:
            if self._last_fatal is not None:
                self._dropped += 1
            self._last_fatal = line
            return
        if self._max_lines >= 10 and level >= logging.ERROR:
            if self._last_error is not None:
                self._dropped += 1
            self._last_error = line
            return
        self._dropped += 1

    def _publish_last(self, line: bytes):
        message = line[:MAX_EVENT_MESSAGE_BYTES].decode('utf-8', errors='replace').rstrip('\r')
        self._logger.log(self._level(message), message, extra=self._extra)

    def _scan_unread_tail(self, output):
        stop_limit = self._stop_limit or output.tell()
        unread = max(0, stop_limit - output.tell())
        self._unscanned_bytes = unread
        if not unread:
            return
        output.seek(max(output.tell(), stop_limit - MAX_STOP_TAIL_BYTES))
        tail = output.read(stop_limit - output.tell())
        last_error = None
        last_fatal = None
        for line in reversed(tail.splitlines()):
            message = line[:MAX_EVENT_MESSAGE_BYTES].decode('utf-8', errors='replace')
            level = self._level(message)
            if level >= logging.CRITICAL and last_fatal is None:
                last_fatal = line
            elif logging.ERROR <= level < logging.CRITICAL and last_error is None:
                last_error = line
            if last_error is not None and last_fatal is not None:
                break
        if last_error is not None:
            self._emit(last_error)
        if last_fatal is not None:
            self._emit(last_fatal)

    def _run(self):
        pending = b''
        truncated = False
        exited = False
        try:
            with open(self._path, 'rb') as output:
                while True:
                    if self._stop.is_set() and (
                        output.tell() >= self._stop_limit or time.monotonic() >= self._stop_deadline
                    ):
                        self._emit(pending)
                        self._scan_unread_tail(output)
                        break
                    fragment = output.readline(MAX_EVENT_MESSAGE_BYTES + 1)
                    if fragment:
                        if truncated:
                            if fragment.endswith(b'\n'):
                                truncated = False
                                self.consumed_offset = output.tell()
                            continue
                        line = pending + fragment
                        if line.endswith(b'\n'):
                            self._emit(line[:-1])
                            pending = b''
                            self.consumed_offset = output.tell()
                        elif len(line) > MAX_EVENT_MESSAGE_BYTES:
                            self._emit(line[:MAX_EVENT_MESSAGE_BYTES])
                            pending = b''
                            truncated = True
                        else:
                            pending = line
                        continue

                    if exited:
                        self._emit(pending)
                        break
                    if self._process.poll() is not None:
                        # Pandora могла дописать вывод между readline() и poll(): дочитываем до EOF.
                        exited = True
                        continue
                    if self._stop.is_set():
                        time.sleep(0.05)
                    else:
                        self._stop.wait(0.05)
        except OSError:
            self.failed = True
            self._logger.warning('Unable to read Pandora output artifact %s', self._path, exc_info=True)
        finally:
            if self.stop_timed_out:
                self._logger.warning('Pandora output reader did not stop within its time budget', extra=self._extra)
            if self._last_error is not None:
                self._publish_last(self._last_error)
            if self._last_fatal is not None:
                self._publish_last(self._last_fatal)
            if self._dropped or self._unscanned_bytes:
                self._logger.warning(
                    'Skipped %s Pandora output lines in event stream; %s unread bytes at stop; full output is in %s',
                    self._dropped,
                    self._unscanned_bytes,
                    self._path,
                    extra=self._extra,
                )


def tail_lines_after(path, offset, lines_num, bufsize=8192):
    """Read the final lines of output that the event reader has not consumed."""
    chunks = []
    newlines = 0
    with open(path, 'rb') as output:
        pos = output.seek(0, os.SEEK_END)
        offset = min(max(offset, 0), pos)
        while pos > offset and newlines <= lines_num:
            step = min(bufsize, pos - offset)
            pos -= step
            output.seek(pos)
            chunk = output.read(step)
            chunks.append(chunk)
            newlines += chunk.count(b'\n')
    tail = b''.join(reversed(chunks))
    if pos > offset:
        newline = tail.find(b'\n')
        tail = tail[newline + 1 :] if newline != -1 else b''
    return tail.decode('utf-8', errors='replace').splitlines()[-lines_num:]
