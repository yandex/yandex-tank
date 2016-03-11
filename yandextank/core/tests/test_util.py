from Queue import Queue
from yandextank.core.util import Drain


class TestDrain(object):
    def test_drain(self):
        source = range(5)
        destination = Queue()
        drain = Drain(source, destination)
        drain.run()
        assert destination.qsize() == 5
