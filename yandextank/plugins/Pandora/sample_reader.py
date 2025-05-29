import fnmatch
import logging
import threading
import os

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from yandextank.common.util import FileMultiReader
from yandextank.plugins.Phantom.reader import PhantomReader


logger = logging.getLogger(__name__)


class SampleWatcher:
    def __init__(self, dir: str, filename_pattern: str):
        self.dir = dir
        self.filename_pattern = filename_pattern
        self.readers: list[SampleReader] = []
        self.observer = Observer()

    def start(self):
        event_handler = FileHandler(self)
        self.observer.schedule(event_handler, self.dir, recursive=False)
        self.observer.start()
        logger.debug('Watching for file %s/%s', self.dir, self.filename_pattern)

    def stop(self):
        self._stop_observer()
        self._stop_readers()

    def _stop_observer(self):
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
            logger.debug('Stop watching for file %s/%s', self.dir, self.filename_pattern)

    def _stop_readers(self):
        for r in self.readers:
            if r.is_alive():
                r.stop()
                r.join()

    def on_file_created(self, path: str):
        if fnmatch.fnmatch(os.path.basename(path), self.filename_pattern):
            reader = SampleReader(path)
            self.readers.append(reader)
            reader.start()


class FileHandler(FileSystemEventHandler):
    def __init__(self, watcher: SampleWatcher):
        self.watcher = watcher

    def on_created(self, event):
        if os.path.isfile(event.src_path):
            self.watcher.on_file_created(event.src_path)


class SampleReader(threading.Thread):
    def __init__(self, logfile_path: str):
        super().__init__()
        self.logfile_path = logfile_path
        self.stop_event = threading.Event()

    def run(self):
        while not (os.path.exists(self.logfile_path) or self.stop_event.wait(0.3)):
            continue

        if self.stop_event.is_set():
            return

        r = FileMultiReader(self.logfile_path, self.stop_event)
        answlog_reader = PhantomReader(r.get_file(), parser=lambda s: s)

        try:
            for sample in answlog_reader:
                if self.stop_event.wait(0.5):
                    break
                if sample is None:
                    continue
                logger.info(sample, extra={'source': 'answlog', 'filepath': self.logfile_path})
        finally:
            r.close()

    def stop(self):
        self.stop_event.set()
