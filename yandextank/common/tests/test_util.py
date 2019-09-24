from threading import Thread, Event

import pytest
from queue import Queue
from yandextank.common.util import FileScanner, FileMultiReader

from netort.data_processing import Drain, Chopper


class TestDrain(object):
    def test_run(self):
        """
        Test drain's run function (in a same thread)
        """
        source = list(range(5))
        destination = Queue()
        drain = Drain(source, destination)
        drain.run()
        assert destination.qsize() == 5

    def test_interrupt(self):
        """
        Test we can interrupt the drain
        """
        source = list(range(1000000))
        destination = Queue()
        drain = Drain(source, destination)
        drain.start()
        drain.close()
        assert destination.qsize() < 1000000

    def test_interrupt_and_wait(self):
        """
        Test we can interrupt the drain
        """
        source = list(range(1000000))
        destination = Queue()
        drain = Drain(source, destination)
        drain.start()
        drain.join()
        assert destination.qsize() == 1000000


class TestChopper(object):
    def test_output(self):
        source = (list(range(i)) for i in range(5))
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


class TestFileMultiReader(object):
    filename = 'yandextank/common/tests/ph.out'

    @staticmethod
    def mock_consumer(f, expected, step, errors):
        for line in [expected[i: i + step] for i in range(0, len(expected), step)]:
            res = f.read(step)
            if line not in res:
                errors.append("Expected: {}\nGot: {}".format(expected, res))

    @staticmethod
    def mock_complex_consumer(f, expected, n_steps, errors):
        for n in range(n_steps):
            f.read()
        res = f.readline() + f.read(10)
        if res != expected:
            errors.append("Expected: {}\nGot: {}".format(expected, res))

    def phout_multi_read(self):
        with open(self.filename) as f:
            exp = f.read()
        errors = []
        stop = Event()
        mr = FileMultiReader(self.filename, stop)
        threads = [Thread(target=self.mock_consumer,
                          args=(mr.get_file(i), exp, i, errors),
                          name='Thread-%d' % i) for i in [1000, 4000, 8000]]
        [th.start() for th in threads]
        stop.set()
        [th.join() for th in threads]
        mr.close()
        return errors

    def phout_multi_readline(self):
        errors = []
        stop = Event()
        mr = FileMultiReader(self.filename, stop)
        threads = [Thread(target=self.mock_complex_consumer,
                          args=(mr.get_file(i), exp, 10, errors),
                          name='Thread-%d' % i) for i, exp in
                   [(1000, '\n1543699431'),
                    (4000, '815\t0\t200\n1543699487'),
                    (8000, '10968\t3633\t16\t7283\t36\t7387\t1066\t328\t0\t405\n1543699534')]]
        [th.start() for th in threads]
        stop.set()
        [th.join() for th in threads]
        mr.close()
        return errors

    @pytest.mark.benchmark(min_rounds=10)
    def test_read(self, benchmark):
        errors = benchmark(self.phout_multi_read)
        assert len(errors) == 0

    @pytest.mark.benchmark(min_rounds=5)
    def test_readline(self, benchmark):
        errors = benchmark(self.phout_multi_readline)
        assert len(errors) == 0
