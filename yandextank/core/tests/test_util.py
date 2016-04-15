from queue import Queue
from yandextank.core.util import Drain


class TestDrain(object):
    def test_run(self):
        """
        Test drain's run function (in a same thread)
        """
        source = range(5)
        destination = Queue()
        drain = Drain(source, destination)
        drain.run()
        assert destination.qsize() == 5

    def test_interrupt(self):
        """
        Test we can interrupt the drain
        """
        source = range(1000000)
        destination = Queue()
        drain = Drain(source, destination)
        drain.start()
        drain.close()
        assert destination.qsize() < 1000000

    def test_interrupt_and_wait(self):
        """
        Test we can interrupt the drain
        """
        source = range(1000000)
        destination = Queue()
        drain = Drain(source, destination)
        drain.start()
        drain.wait()
        assert destination.qsize() == 1000000
