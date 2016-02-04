import unittest

from yandextank.plugins.Phantom.reader import PhantomReader
from contextlib import closing
import threading
import time
import logging
import tempfile
import os

phantom_config = {
    "interval_real": ["total", "max", "min", "hist", "len"],
    "connect_time": ["total", "max", "min", "len"],
    "send_time": ["total", "max", "min", "len"],
    "latency": ["total", "max", "min", "len"],
    "receive_time": ["total", "max", "min", "len"],
    "interval_event": ["total", "max", "min", "len"],
    "size_out": ["total", "max", "min", "len"],
    "size_in": ["total", "max", "min", "len"],
    "net_code": ["count"],
    "proto_code": ["count"],
}

LOG = logging.getLogger(__name__)


class Writer(threading.Thread):
    def __init__(self, file):
        super(Writer, self).__init__()
        self.file = file
        self.finished = False

    def run(self):
        with open("data/phout_example.txt") as ph_source:
            chunk = ph_source.read(1024)
            while chunk:
                LOG.info("Writing chunk to file")
                self.file.write(chunk)
                self.file.flush()
                chunk = ph_source.read(1024)
                time.sleep(0.4)
        self.finished = True


class ReaderTestCase(unittest.TestCase):
    def test_reader(self):
        _, filepath = tempfile.mkstemp()
        print(filepath)
        with open(filepath, 'w') as phout_write:
            with closing(PhantomReader(filepath)) as reader:
                writer = Writer(phout_write)
                writer.start()
                while not writer.finished:
                    time.sleep(1)
                    print(reader.read_chunk())
        os.unlink(filepath)


if __name__ == '__main__':
    unittest.main()
