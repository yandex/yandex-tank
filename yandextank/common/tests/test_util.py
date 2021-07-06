import socket
from threading import Thread, Event

import mock
import paramiko
import pytest
from queue import Queue
from yandextank.common.util import FileScanner, FileMultiReader
from yandextank.common.util import AddressWizard, SecuredShell
from yandextank.common.tests.ssh_client import SSHClientWithBanner, SSHClientWithoutBanner

from netort.data_processing import Drain, Chopper

banner = '###Hellow user!####\n'


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
        # return format: is_v6, parsed_ip, int(port), address_str
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

    @pytest.mark.skip('no module in arcadia')
    @pytest.mark.benchmark(min_rounds=10)
    def test_read(self, benchmark):
        errors = benchmark(self.phout_multi_read)
        assert len(errors) == 0

    @pytest.mark.skip('no module in arcadia')
    @pytest.mark.benchmark(min_rounds=5)
    def test_readline(self, benchmark):
        errors = benchmark(self.phout_multi_readline)
        assert len(errors) == 0


class TestSecuredShell(object):

    def test_check_empty_banner(self):
        with mock.patch.object(SecuredShell, 'connect', SSHClientWithoutBanner):
            with mock.patch.object(paramiko.SSHClient, 'exec_command', SSHClientWithoutBanner.exec_command):
                output, _, _ = SecuredShell(None, None, None).execute('pwd')
                assert SecuredShell(None, None, None).check_banner() == ''
                assert output == '/var/tmp'

    def test_check_banner(self):
        with mock.patch.object(SecuredShell, 'connect', SSHClientWithBanner):
            with mock.patch.object(paramiko.SSHClient, 'exec_command', SSHClientWithBanner.exec_command):
                output, _, _ = SecuredShell(None, None, None).execute('pwd')
                assert SecuredShell(None, None, None).check_banner() == banner
                assert output == '/var/tmp'
