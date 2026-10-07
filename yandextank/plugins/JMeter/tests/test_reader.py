from yandextank.aggregator.aggregator import DataPoller
from yandextank.plugins.JMeter.reader import JMeterReader

LINE = '1791300000000\t25\tYA04_wait_for_acquire\t200\ttrue\t512\t5\t5\t20\t3\n'.encode()


def make_reader(path='unused.jtl'):
    return JMeterReader(str(path), DataPoller(poll_period=0.01, max_wait=1))


class JtlAppendedAfterEof:
    """Файл, в который JMeter дописывает строку сразу после того, как read() вернул EOF."""

    def __init__(self):
        self._pending = b''
        self._appended = False

    def read(self, size=-1):
        data, self._pending = self._pending, b''
        if not data and not self._appended:
            self._appended = True
            self._pending = LINE
        return data

    def readline(self):
        data, self._pending = self._pending, b''
        return data


def test_line_written_right_after_eof_is_not_lost():
    reader = make_reader()
    jtl = JtlAppendedAfterEof()

    assert reader._read_jtl_chunk(jtl) is None
    df = reader._read_jtl_chunk(jtl)

    assert df is not None
    assert list(df['tag']) == ['YA04_wait_for_acquire']


def test_utf8_char_cut_at_end_of_file(tmp_path):
    line = '1791300000000\t25\tПроверка\t200\ttrue\t512\t5\t5\t20\t3\n'.encode()
    cut = line.index('р'.encode()) + 1  # JMeter успел записать только первый байт буквы
    jtl = tmp_path / 'test.jtl'
    jtl.write_bytes(line[:cut])
    chunks = iter(make_reader(jtl))

    assert next(chunks) is None
    assert next(chunks) is None
    with open(jtl, 'ab') as f:
        f.write(line[cut:])
    df = next(chunks)

    assert list(df['tag']) == ['Проверка']
