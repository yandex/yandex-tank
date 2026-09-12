import socket
import yatest.common
from threading import Thread, Event

import pytest
from queue import Queue
from yandextank.common.util import FileScanner, FileMultiReader
from yandextank.common.util import AddressWizard, SecuredShell
from yandextank.common.util import expand_to_milliseconds, expand_to_seconds

from load.contrib.netort.data_processing import Drain, Chopper


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
    filename = yatest.common.source_path('load/projects/yandex-tank/yandextank/common/tests/ph.out')

    @staticmethod
    def mock_consumer(f, expected, step, errors):
        for line in [expected[i : i + step] for i in range(0, len(expected), step)]:
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
        threads = [
            Thread(target=self.mock_consumer, args=(mr.get_file(i), exp, i, errors), name='Thread-%d' % i)
            for i in [1000, 4000, 8000]
        ]
        [th.start() for th in threads]
        stop.set()
        [th.join() for th in threads]
        mr.close()
        return errors

    def phout_multi_readline(self):
        errors = []
        stop = Event()
        mr = FileMultiReader(self.filename, stop)
        threads = [
            Thread(target=self.mock_complex_consumer, args=(mr.get_file(i), exp, 10, errors), name='Thread-%d' % i)
            for i, exp in [
                (1000, '\n1543699431'),
                (4000, '815\t0\t200\n1543699487'),
                (8000, '10968\t3633\t16\t7283\t36\t7387\t1066\t328\t0\t405\n1543699534'),
            ]
        ]
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


class TestSecuredShell(object):

    def test_ssh_path(self):
        s = SecuredShell(None, None, None, command_timeout=10, ssh_key_path=".")
        assert s.key_filename is not None

    def test_username_keeps_default_ssh_opts(self):
        opts = SecuredShell('somehost', 2222, 'nobody')._make_ssh_opts()
        assert 'user="nobody"' in opts
        assert 'StrictHostKeyChecking=no' in opts
        assert 'BatchMode=yes' in opts
        assert opts[opts.index('-p') + 1] == '2222'


class TestExpandTime:
    """Разбор длительности из конфига.

    Это число задаёт длительность стрельбы (TimeLimitCriterion), пороги автостопа,
    таймауты и интервалы опроса агентов — больше двадцати мест. Ошибка здесь не падает,
    а тихо меняет условия прогона, поэтому проверяется не «разобралось», а точное значение.
    """

    @pytest.mark.parametrize(
        'value,expected',
        [
            ('1', 1),
            ('60', 60),
            ('1s', 1),
            ('1m', 60),
            ('1h', 3600),
            ('1d', 86400),
            ('1w', 604800),
            ('1h30m', 5400),
            ('1m30s', 90),
            ('1M', 60),  # регистр единицы не важен: M это минуты, не месяцы
        ],
    )
    def test_whole_units(self, value, expected):
        assert expand_to_seconds(value) == expected

    @pytest.mark.parametrize(
        'value,expected',
        [
            ('1.5m', 90),
            ('0.5m', 30),
            ('2.5h', 9000),
            ('1.5s', 1),  # результат целый, дробь секунды отбрасывается
        ],
    )
    def test_fractional_values(self, value, expected):
        """Дробь читается как часть числа.

        До LOAD-3696 regex не знал точки, поэтому '1.5m' распадался на 1s и 5m и давал
        301 секунду вместо 90 — стрельба шла впятеро дольше запрошенного.
        """
        assert expand_to_seconds(value) == expected

    def test_subsecond_in_seconds_is_zero(self):
        """Секундный разбор не умеет субсекунду — и это должно быть видно в тесте.

        Именно отсюда берётся нулевой интервал опроса у агентов, если в конфиге указать
        '500ms': за субсекундными значениями надо идти в expand_to_milliseconds.
        """
        assert expand_to_seconds('500ms') == 0
        assert expand_to_milliseconds('500ms') == 500

    def test_same_literal_means_same_time_in_both_helpers(self):
        """Один литерал — одно и то же время, с точностью до единиц измерения.

        До починки '1.5s' давал 5 секунд в одной обёртке и 5001 миллисекунду в другой:
        расхождение в тысячу раз на ровном месте.
        """
        assert expand_to_milliseconds('1.5s') == 1500
        assert expand_to_milliseconds('2m') == 120000
        assert expand_to_milliseconds('60') == 60  # голое число здесь миллисекунды

    def test_unknown_unit_raises(self):
        with pytest.raises(ValueError):
            expand_to_seconds('5x')

    def test_garbage_without_digits_raises(self):
        """Опечатка в конфиге обязана падать, а не превращаться в нулевой таймаут."""
        with pytest.raises(ValueError):
            expand_to_seconds('abc')

    def test_negative_duration_raises(self):
        """'-1' раньше разбиралось как '1': минус не попадал в regex."""
        with pytest.raises(ValueError):
            expand_to_seconds('-1')
        with pytest.raises(ValueError):
            expand_to_seconds('-1m')

    def test_empty_string_is_zero(self):
        """Пустое значение — это «не задано», исторически ноль; менять не стали."""
        assert expand_to_seconds('') == 0
