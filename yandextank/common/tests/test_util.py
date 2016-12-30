from queue import Queue
from yandextank.common.util import Drain, Chopper


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
        drain.join()
        assert destination.qsize() == 1000000


class TestChopper(object):
    def test_output(self):
        source = (range(i) for i in range(5))
        expected = [0, 0, 1, 0, 1, 2, 0, 1, 2, 3]
        assert list(Chopper(source)) == expected
