from queue import Queue
from yandextank.common.util import FileScanner
import socket

from netort.data_processing import Drain, Chopper
from yandextank.common.util import AddressWizard


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


class TestAddressResolver(object):
    @staticmethod
    def __resolve(chunk):
        aw = AddressWizard()
        return aw.resolve(chunk)

    def __resolve_hostname_and_test(self, address_str, test_hostname, test_port):
        passed = False
        try:
            resolved = socket.getaddrinfo(test_hostname, test_port)
        except Exception:
            # skip this check if resolver not available
            return True

        try:
            for i in resolved:
                if i[4][1] == self.__resolve(address_str)[2] and i[4][0] == self.__resolve(address_str)[1]:
                    passed = True
        except IndexError:
            pass
        assert passed

    # ipv6
    def test_ipv6(self):
        assert self.__resolve('2a02:6b8::2:242') == (True, '2a02:6b8::2:242', 80, '2a02:6b8::2:242')

    def test_ipv6_braces_port(self):
        assert self.__resolve('[2a02:6b8::2:242]:666') == (True, '2a02:6b8::2:242', 666, '2a02:6b8::2:242')

    def test_ipv6_braces_port_spaces(self):
        assert self.__resolve('[ 2a02:6b8::2:242 ]: 666') == (True, '2a02:6b8::2:242', 666, '2a02:6b8::2:242')

    def test_ipv4(self):
        assert self.__resolve('87.250.250.242') == (False, '87.250.250.242', 80, '87.250.250.242')

    def test_ipv4_port(self):
        assert self.__resolve('87.250.250.242:666') == (False, '87.250.250.242', 666, '87.250.250.242')

    def test_ipv4_braces_port(self):
        assert self.__resolve('[87.250.250.242]:666') == (False, '87.250.250.242', 666, '87.250.250.242')

    # hostname
    def test_hostname_port(self):
        self.__resolve_hostname_and_test('ya.ru:666', 'ya.ru', '666')

    def test_hostname_braces(self):
        self.__resolve_hostname_and_test('[ya.ru]', 'ya.ru', '80')

    def test_hostname_braces_port(self):
        self.__resolve_hostname_and_test('[ya.ru]:666', 'ya.ru', '666')
