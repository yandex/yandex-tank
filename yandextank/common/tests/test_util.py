import errno
import os
import signal
import socket
import subprocess
import yatest.common
from threading import Thread, Event
from unittest import mock

import pytest
from queue import Queue
from yandextank.common.util import FileScanner, FileMultiReader
from yandextank.common.util import AddressWizard, SecuredShell, Session
from yandextank.common.util import expand_to_milliseconds, expand_to_seconds
from yandextank.common.util import Cleanup, Finish, Status
from yandextank.common.util import get_ssh_key_filenames, pid_exists, tail_lines

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

    def test_iter_follows_growing_file_until_closed(self, tmp_path):
        class LinesScanner(FileScanner):
            def _read_data(self, lines):
                return list(lines)

        stats = tmp_path / 'stats'
        stats.write_text('a\nb\nc')
        scanner = LinesScanner(str(stats))
        chunks = iter(scanner)
        assert next(chunks) == ['a', 'b']
        # EOF не конец чтения: генератор дописывает файл, пока плагин не закрыл читателя
        assert next(chunks) == []
        with open(stats, 'a') as f:
            f.write('\nd\n')
        assert next(chunks) == ['c', 'd']
        scanner.close()
        with pytest.raises(StopIteration):
            next(chunks)


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


class TestAddressWizardDecisions:
    @staticmethod
    def _wizard(*sockaddrs):
        aw = AddressWizard()
        aw.lookup_fn = mock.Mock(return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, '', sa) for sa in sockaddrs])
        aw.socket_class = mock.Mock()
        return aw

    @pytest.mark.parametrize('address', ['', None])
    def test_missing_address_raises(self, address):
        with pytest.raises(RuntimeError):
            AddressWizard().resolve(address)

    def test_lookup_error_is_not_swallowed(self):
        aw = AddressWizard()
        aw.lookup_fn = mock.Mock(side_effect=socket.gaierror('Name or service not known'))
        with pytest.raises(socket.gaierror):
            aw.resolve('no-such-host.invalid')

    def test_explicit_port_overrides_port_from_address(self):
        aw = self._wizard(('10.0.0.1', 443))
        assert aw.resolve('target:443', explicit_port='8080') == (False, '10.0.0.1', 8080, 'target')
        aw.lookup_fn.assert_called_once_with('target', 443)

    def test_connection_test_skips_unreachable_address(self):
        aw = self._wizard(('10.0.0.1', 0), ('10.0.0.2', 0))
        sock = aw.socket_class.return_value
        sock.connect.side_effect = [ConnectionRefusedError(), None]
        assert aw.resolve('target', do_test=True) == (False, '10.0.0.2', 80, 'target')
        assert sock.connect.call_args_list == [mock.call(('10.0.0.1', 80)), mock.call(('10.0.0.2', 80))]
        assert sock.close.call_count == 2

    def test_connection_test_fails_when_nothing_reachable(self):
        aw = self._wizard(('10.0.0.1', 0), ('10.0.0.2', 0))
        aw.socket_class.return_value.connect.side_effect = ConnectionRefusedError()
        with pytest.raises(RuntimeError, match='All connection attempts failed for target'):
            aw.resolve('target', do_test=True)


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

    @pytest.fixture
    def which(self):
        # ssh и scp в песочнице тестов может не быть, а проверка наличия идёт до запуска
        with mock.patch('yandextank.common.util.shutil.which', return_value='/usr/bin/tool') as which:
            yield which

    @staticmethod
    def _shell(returncode=0, stderr=b''):
        shell = SecuredShell('somehost', 2222, 'nobody')
        process = mock.Mock(returncode=returncode)
        process.communicate.return_value = (b'', stderr)
        shell.popen = mock.Mock(return_value=process)
        return shell

    def test_missing_executable_raises_before_running(self, which):
        which.return_value = None
        shell = self._shell()
        with pytest.raises(FileNotFoundError, match='ssh executable'):
            shell.execute('exit')
        shell.popen.assert_not_called()

    def test_valid_key_is_passed_first(self):
        shell = SecuredShell('somehost', 2222, 'nobody')
        shell.valid_key = '/keys/id_rsa'
        assert shell._make_ssh_opts()[:2] == ['-i', '/keys/id_rsa']

    @pytest.mark.parametrize(
        'explicit, default, exit_codes, expected',
        [
            (['/a', '/b', '/c'], ['/d'], [255, 0], '/b'),
            (None, ['/d'], [0], '/d'),
            (['/a'], ['/d'], [255], None),  # явные ключи не откатываются на ~/.ssh
        ],
    )
    def test_pick_ssh_key(self, explicit, default, exit_codes, expected):
        shell = SecuredShell('somehost', 2222, 'nobody')
        shell.key_filename, shell.default_key_filename = explicit, default
        shell.execute = mock.Mock(side_effect=[('', '', code) for code in exit_codes])
        assert shell._pick_ssh_key() == expected
        assert shell.execute.call_count == len(exit_codes)

    def test_timeout_kills_process_and_reports_failure(self):
        process = mock.Mock()
        process.communicate.side_effect = subprocess.TimeoutExpired('ssh', 1)
        shell = SecuredShell('somehost', 2222, 'nobody')
        assert shell._safe_communicate(process, 1, 'timeout') == (b'', b'', 1)
        process.kill.assert_called_once_with()

    @pytest.mark.parametrize(
        'method, args, cmd_tail',
        [
            ('send_file', ('/local/f', '/remote/f'), '/local/f somehost:/remote/f'),
            ('get_file', ('/remote/f', '/local/f'), 'somehost:/remote/f /local/f'),
        ],
    )
    def test_file_transfer_command(self, which, method, args, cmd_tail):
        shell = self._shell()
        getattr(shell, method)(*args)
        which.assert_called_once_with('scp')
        cmd = shell.popen.call_args.args[0]
        assert cmd.startswith('scp -P 2222 ')
        assert cmd.endswith(cmd_tail)

    @pytest.mark.parametrize('method', ['send_file', 'get_file'])
    def test_file_transfer_failure_raises(self, which, method):
        shell = self._shell(returncode=1, stderr=b'Permission denied')
        with pytest.raises(ConnectionError, match='Permission denied'):
            getattr(shell, method)('/a', '/b')

    @pytest.mark.parametrize('path', ['', None, '/'])
    def test_rm_r_refuses_empty_and_root(self, path):
        shell = SecuredShell('somehost', 2222, 'nobody')
        shell.execute = mock.Mock()
        with pytest.raises(ValueError):
            shell.rm_r(path)
        shell.execute.assert_not_called()

    def test_rm_r_removes_given_path(self):
        shell = SecuredShell('somehost', 2222, 'nobody')
        shell.execute = mock.Mock(return_value=('', '', 0))
        assert shell.rm_r('/tmp/agent') == ('', '', 0)
        shell.execute.assert_called_once_with('rm -rf /tmp/agent')


class TestSession:
    @staticmethod
    def _session(shell_cmd):
        client = mock.Mock()
        client.execute_without_communicate.return_value = SecuredShell.popen(shell_cmd)
        return Session(client, 'agent')

    def test_close_kills_process_that_did_not_exit(self):
        session = self._session('exec sleep 30')
        assert not session.is_finished()
        session.close(timeout=0.1)
        assert session.process.wait(timeout=5) == -signal.SIGKILL
        assert session.is_finished()

    def test_send_is_dropped_after_process_finished(self):
        session = self._session('exit 3')
        session.process.wait(timeout=5)
        session.process.stdin = mock.Mock()
        session.send(b'data')
        session.process.stdin.write.assert_not_called()
        assert session.exit_status() == 3


class TestGetSshKeyFilenames:
    def test_lists_only_files(self, tmp_path):
        (tmp_path / 'id_rsa').write_text('key')
        (tmp_path / 'subdir').mkdir()
        assert get_ssh_key_filenames(str(tmp_path)) == [str(tmp_path / 'id_rsa')]

    @pytest.mark.parametrize('path', ['', None, '/nonexistent/ssh/keys'])
    def test_no_usable_path_means_no_keys(self, path):
        assert get_ssh_key_filenames(path) == []


class TestPidExists:
    def test_negative_pid(self):
        assert pid_exists(-1) is False

    def test_current_process(self):
        assert pid_exists(os.getpid()) is True

    @pytest.mark.parametrize('code, expected', [(errno.ESRCH, False), (errno.EPERM, True)])
    def test_kill_error(self, code, expected):
        # EPERM: процесс есть, но чужой — лок живого теста снимать нельзя
        with mock.patch('yandextank.common.util.os.kill', side_effect=OSError(code, os.strerror(code))):
            assert pid_exists(12345) is expected

    def test_zombie_is_not_alive(self):
        # Зомби отвечает на kill(pid, 0), но лок от него надо снимать
        proc = subprocess.Popen(['true'])
        try:
            os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOWAIT)  # дождаться выхода, не забирая процесс
            assert pid_exists(proc.pid) is False
        finally:
            proc.wait()


class TestTailLines:
    # 20 не кратно длине строки: граница буфера рвёт строку посередине
    @pytest.mark.parametrize('bufsize', [20, 8192])  # буфер меньше и больше файла
    def test_returns_last_full_lines(self, tmp_path, bufsize):
        log = tmp_path / 'stderr'
        log.write_text(''.join('line%03d\n' % i for i in range(100)))
        assert tail_lines(str(log), 3, bufsize=bufsize) == ['line097\n', 'line098\n', 'line099\n']

    @pytest.mark.parametrize('bufsize', [1, 8192])
    @pytest.mark.parametrize(
        'content, lines_num, expected',
        [
            ('', 5, []),
            ('x', 5, ['x']),
            ('\n', 1, ['\n']),
            ('aaa\nbbb\nccc\n', 3, ['aaa\n', 'bbb\n', 'ccc\n']),
            ('a\nb\nc\n', 10, ['a\n', 'b\n', 'c\n']),
            ('a\nb', 1, ['b']),
        ],
    )
    def test_short_file(self, tmp_path, content, lines_num, expected, bufsize):
        log = tmp_path / 'stderr'
        log.write_text(content)
        result = []
        # На пустом файле функция раньше зацикливалась: ждём в потоке, чтобы не повесить прогон
        worker = Thread(target=lambda: result.append(tail_lines(str(log), lines_num, bufsize=bufsize)), daemon=True)
        worker.start()
        worker.join(5)
        assert result == [expected]

    def test_lines_longer_than_buffer(self, tmp_path):
        lines = ['%02d%s\n' % (i, 'x' * 1000) for i in range(30)]
        log = tmp_path / 'stderr'
        log.write_text(''.join(lines))
        assert tail_lines(str(log), 20) == lines[-20:]


class TestCleanup:
    def test_runs_actions_in_reverse_despite_failures(self):
        worker = mock.Mock(retcode=0)
        done = []

        # Своё исключение, а не OSError: сужение except до встроенных типов должно ронять тест
        class LockGone(Exception):
            pass

        def broken():
            raise LockGone('lock is gone')

        with Cleanup(worker) as add_cleanup:
            add_cleanup('first', lambda: done.append('first'))
            add_cleanup('release lock', broken)
            add_cleanup('last', lambda: done.append('last'))

        assert done == ['last', 'first']
        assert worker.retcode == 0
        msgs = worker.add_msgs.call_args.args
        assert len(msgs) == 1 and 'release lock' in msgs[0]
        worker.save_finish_status.assert_called_once_with()
        worker.core._collect_artifacts.assert_called_once_with()
        worker.core.close.assert_called_once_with()
        assert worker.status == Status.TEST_FINISHED

    def test_exception_sets_retcode_and_is_reraised(self):
        worker = mock.Mock(retcode=0)
        with pytest.raises(ValueError):
            with Cleanup(worker):
                raise ValueError('config is broken')
        assert worker.retcode == 1
        assert 'config is broken' in worker.add_msgs.call_args.args[0]
        worker.core.close.assert_called_once_with()


class TestFinish:
    def test_exception_is_swallowed_and_reported_as_failure(self):
        worker = mock.Mock(retcode=0)
        worker.core.plugins_end_test.return_value = 21
        with Finish(worker):
            raise RuntimeError('shooting failed')
        worker.core.plugins_end_test.assert_called_once_with(1)
        assert worker.retcode == 21
        assert worker.status == Status.TEST_FINISHING
        assert 'shooting failed' in worker.add_msgs.call_args.args[0]

    def test_normal_exit_passes_current_retcode(self):
        worker = mock.Mock(retcode=0)
        worker.core.plugins_end_test.return_value = 0
        with Finish(worker):
            worker.retcode = 3
        worker.core.plugins_end_test.assert_called_once_with(3)
        assert worker.retcode == 0
        worker.add_msgs.assert_not_called()


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
        assert expand_to_milliseconds('2.01s') == 2010  # во float 2.01*1000 = 2009.999…
        assert expand_to_milliseconds('8030ms') == 8030
        assert expand_to_seconds('1.5s') == 1  # до секунд по-прежнему отбрасывается дробная часть

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
