from queue import Queue
from yandextank.common.util import Drain, Chopper, FileScanner


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


class TestFileScanner(object):
    @staticmethod
    def __process_chunks(chunks, sep="\n"):
        reader = FileScanner("somefile.txt", sep=sep)
        result = []
        for chunk in chunks:
            result.extend(reader._read_lines(chunk))
        return result

    def test_empty(self):
        assert self.__process_chunks([""]) == []

    def test_simple(self):
        assert self.__process_chunks(["aaa\n", "bbb\n", "ccc\n"]) == ["aaa", "bbb", "ccc"]

    def test_split(self):
        assert self.__process_chunks(["aaa\nbbb\n", "ccc\n"]) == ["aaa", "bbb", "ccc"]

    def test_join(self):
        assert self.__process_chunks(["aaa", "bbb\n", "ccc\n"]) == ["aaabbb", "ccc"]

    def test_no_first_separator(self):
        assert self.__process_chunks(["aaa"]) == []

    def test_no_last_separator(self):
        assert self.__process_chunks(["aaa\n", "bbb\n", "ccc"]) == ["aaa", "bbb"]

    def test_use_custom_separator(self):
        assert self.__process_chunks(["aaa:bbb:ccc:"], ":") == ["aaa", "bbb", "ccc"]
