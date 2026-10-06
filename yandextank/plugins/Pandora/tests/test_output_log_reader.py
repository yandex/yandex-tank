import io
import logging
import time
from threading import Event
from unittest.mock import Mock, patch

import pytest

from yandextank.plugins.Pandora.output_log_reader import (
    MAX_EVENT_MESSAGE_BYTES,
    PandoraOutputReader,
    tail_lines_after,
)


class RecordCollector(logging.Handler):
    def __init__(self, delay=0):
        super().__init__()
        self.records = []
        self.received = Event()
        self.delay = delay

    def emit(self, record):
        self.records.append(record)
        self.received.set()
        if self.delay:
            time.sleep(self.delay)


def make_logger(delay=0):
    logger = logging.getLogger('pandora-output-reader-test')
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    collector = RecordCollector(delay)
    logger.addHandler(collector)
    return logger, collector


def test_running_process_forwards_lines_and_preserves_artifact(tmp_path):
    output = tmp_path / 'pandora.log'
    output.write_text('INFO started\n')
    process = Mock()
    process.poll.return_value = None
    logger, collector = make_logger()
    reader = PandoraOutputReader(str(output), process, logger)

    reader.start()
    assert collector.received.wait(1)
    with output.open('a') as artifact:
        artifact.write('ERROR failed\n')
    process.poll.return_value = 1
    reader._thread.join(timeout=1)
    reader.stop()

    assert [record.getMessage() for record in collector.records] == ['INFO started', 'ERROR failed']
    assert [record.levelno for record in collector.records] == [logging.INFO, logging.ERROR]
    assert all(record.source == 'pandora' for record in collector.records)
    assert output.read_text() == 'INFO started\nERROR failed\n'
    assert reader.consumed_offset == output.stat().st_size


def test_noisy_output_is_bounded_and_reports_dropped_lines(tmp_path):
    output = tmp_path / 'pandora.log'
    output.write_text(''.join(f'line {index}\n' for index in range(5)))
    process = Mock()
    process.poll.return_value = 0
    logger, collector = make_logger()
    reader = PandoraOutputReader(str(output), process, logger, max_lines=2)

    reader.start()
    reader._thread.join(timeout=1)
    reader.stop()

    assert [record.getMessage() for record in collector.records[:2]] == ['line 0', 'line 1']
    assert collector.records[-1].levelno == logging.WARNING
    assert 'Skipped 3 Pandora output lines' in collector.records[-1].getMessage()
    assert len(output.read_text().splitlines()) == 5


def test_stop_does_not_wait_for_stuck_process(tmp_path):
    output = tmp_path / 'pandora.log'
    output.touch()
    process = Mock()
    process.poll.return_value = None
    logger, _ = make_logger()
    reader = PandoraOutputReader(str(output), process, logger)

    reader.start()
    started = time.monotonic()
    reader.stop()

    assert time.monotonic() - started < 1
    assert not reader._thread.is_alive()
    started = time.monotonic()
    reader.stop()
    assert time.monotonic() - started < 0.2


def test_late_fatal_is_visible_after_normal_line_budget(tmp_path):
    output = tmp_path / 'pandora.log'
    output.write_text('INFO noise\n' * 1000 + 'FATAL last failure\n')
    process = Mock()
    process.poll.return_value = 1
    logger, collector = make_logger()
    reader = PandoraOutputReader(str(output), process, logger)

    reader.start()
    reader._thread.join(timeout=2)
    reader.stop()

    assert any(record.getMessage() == 'FATAL last failure' for record in collector.records)
    assert sum(record.getMessage() == 'INFO noise' for record in collector.records) == 998
    assert 'Skipped 2 Pandora output lines' in collector.records[-1].getMessage()


def test_last_error_is_preserved_after_noisy_crash(tmp_path):
    output = tmp_path / 'pandora.log'
    output.write_text('INFO noise\n' * 1000 + 'ERROR retry\nERROR final failure\n')
    process = Mock()
    process.poll.return_value = 2
    logger, collector = make_logger()
    reader = PandoraOutputReader(str(output), process, logger)

    reader.start()
    reader._thread.join(timeout=2)
    reader.stop()

    messages = [record.getMessage() for record in collector.records]
    assert 'ERROR final failure' in messages
    assert 'ERROR retry' not in messages
    assert messages.count('ERROR final failure') == 1
    assert 'Skipped 3 Pandora output lines' in messages[-1]


def test_debug_output_does_not_hide_later_info_at_default_level(tmp_path):
    output = tmp_path / 'pandora.log'
    output.write_text('DEBUG noise\n' * 1000 + 'INFO useful line\n')
    process = Mock()
    process.poll.return_value = 0
    logger, collector = make_logger()
    logger.setLevel(logging.INFO)
    reader = PandoraOutputReader(str(output), process, logger)

    reader.start()
    reader._thread.join(timeout=2)
    reader.stop()

    assert [record.getMessage() for record in collector.records] == ['INFO useful line']


def test_info_sink_still_receives_info_after_debug_flood(tmp_path):
    output = tmp_path / 'pandora.log'
    output.write_text('DEBUG noise\n' * 1000 + 'INFO useful line\n')
    process = Mock()
    process.poll.return_value = 0
    logger, collector = make_logger()
    collector.setLevel(logging.INFO)
    reader = PandoraOutputReader(str(output), process, logger)

    reader.start()
    reader._thread.join(timeout=2)
    reader.stop()

    messages = [record.getMessage() for record in collector.records]
    assert 'INFO useful line' in messages
    assert 'DEBUG noise' not in messages


def test_backlog_tail_keeps_fatal_and_later_cleanup_error(tmp_path):
    output = tmp_path / 'pandora.log'
    output.write_bytes(b'INFO noise\n' * 200_000 + b'FATAL root cause\nERROR cleanup\n')
    process = Mock()
    process.poll.return_value = None
    logger, collector = make_logger(delay=0.001)
    reader = PandoraOutputReader(str(output), process, logger)

    reader.start()
    assert collector.received.wait(1)
    reader.stop()

    messages = [record.getMessage() for record in collector.records]
    assert 'FATAL root cause' in messages
    assert 'ERROR cleanup' in messages
    assert messages.count('FATAL root cause') == 1
    assert messages.count('ERROR cleanup') == 1


def test_backlog_tail_keeps_real_error_after_two_fatals(tmp_path):
    output = tmp_path / 'pandora.log'
    output.write_bytes(b'INFO noise\n' * 200_000 + b'ERROR root\nFATAL first\nFATAL last\n')
    process = Mock()
    process.poll.return_value = None
    logger, collector = make_logger(delay=0.001)
    reader = PandoraOutputReader(str(output), process, logger)

    reader.start()
    assert collector.received.wait(1)
    reader.stop()

    messages = [record.getMessage() for record in collector.records]
    assert 'ERROR root' in messages
    assert 'FATAL last' in messages
    assert 'FATAL first' not in messages


def test_stop_with_backlog_reports_unread_bytes_and_captures_fatal_tail(tmp_path):
    output = tmp_path / 'pandora.log'
    output.write_bytes(b'INFO noise\n' * 200_000 + b'FATAL last failure\n')
    process = Mock()
    process.poll.return_value = None
    logger, collector = make_logger(delay=0.001)
    reader = PandoraOutputReader(str(output), process, logger)

    reader.start()
    assert collector.received.wait(1)
    started = time.monotonic()
    reader.stop()

    assert time.monotonic() - started < 1
    assert not reader._thread.is_alive()
    assert reader._unscanned_bytes > 0
    assert any(record.getMessage() == 'FATAL last failure' for record in collector.records)
    assert 'unread bytes at stop' in collector.records[-1].getMessage()


def test_stop_does_not_log_synchronously_while_handler_is_busy(tmp_path):
    output = tmp_path / 'pandora.log'
    output.write_text('INFO slow handler\n')
    process = Mock()
    process.poll.return_value = None
    logger, _ = make_logger()
    entered = Event()
    release = Event()

    class BusyHandler(logging.Handler):
        def emit(self, record):
            if record.getMessage() == 'INFO slow handler':
                entered.set()
                release.wait(2)

    logger.addHandler(BusyHandler())
    reader = PandoraOutputReader(str(output), process, logger)
    reader.start()
    assert entered.wait(1)

    try:
        started = time.monotonic()
        reader.stop()
        assert time.monotonic() - started < 1
        assert reader.stop_timed_out
    finally:
        release.set()
        reader._thread.join(timeout=2)

    assert not reader._thread.is_alive()


@pytest.mark.parametrize(
    'line, expected_level',
    [
        ('2026-10-05T12:00:00.000Z\tDEBUG\tgun.go:42\trequest\t{"error":"retry"}', logging.DEBUG),
        ('2026-10-05 12:00:00 [INFO] message with FATAL in payload', logging.INFO),
        ('ERROR failed', logging.ERROR),
        ('2026-10-05T12:00:00.000Z\tWARN\ttemporary failure', logging.WARNING),
        ('panic: worker crashed', logging.CRITICAL),
        ('2026-10-05T12:00:00.000Z\tPANIC\tgun.go:42\tfailed', logging.CRITICAL),
        ('2026-10-05T12:00:00.000Z\tDPANIC\tgun.go:42\tfailed', logging.CRITICAL),
        ('request returned {"error":"retry"}', logging.INFO),
    ],
)
def test_level_is_read_from_log_header(line, expected_level):
    assert PandoraOutputReader._level(line) == expected_level


def test_debug_payload_error_does_not_replace_real_error(tmp_path):
    output = tmp_path / 'pandora.log'
    debug_line = '2026-10-05T12:00:00.000Z\tDEBUG\tgun.go:42\trequest\t{"error":"retry"}'
    output.write_text('INFO noise\n' * 998 + 'ERROR actual failure\n' + debug_line + '\n')
    process = Mock()
    process.poll.return_value = 1
    logger, collector = make_logger()
    reader = PandoraOutputReader(str(output), process, logger)

    reader.start()
    reader._thread.join(timeout=2)
    reader.stop()

    messages = [record.getMessage() for record in collector.records]
    assert messages.count('ERROR actual failure') == 1
    assert debug_line not in messages


def test_partial_line_is_forwarded_once_after_newline(tmp_path):
    output = tmp_path / 'pandora.log'
    output.write_bytes(b'INFO par')
    process = Mock()
    process.poll.return_value = None
    logger, collector = make_logger()
    reader = PandoraOutputReader(str(output), process, logger)
    first_read = Event()
    real_open = open

    def observed_open(path, mode):
        file_handle = real_open(path, mode)

        class ObservedFile:
            def __enter__(self):
                file_handle.__enter__()
                return self

            def __exit__(self, *args):
                return file_handle.__exit__(*args)

            def __getattr__(self, name):
                return getattr(file_handle, name)

            def readline(self, *args):
                fragment = file_handle.readline(*args)
                if fragment == b'INFO par':
                    first_read.set()
                return fragment

        return ObservedFile()

    with patch('yandextank.plugins.Pandora.output_log_reader.open', side_effect=observed_open, create=True):
        reader.start()
        assert first_read.wait(1)
        assert not collector.records
        with output.open('ab') as artifact:
            artifact.write(b'tial\n')
        process.poll.return_value = 0
        reader._thread.join(timeout=1)
        reader.stop()

    assert not reader._thread.is_alive()
    assert [record.getMessage() for record in collector.records] == ['INFO partial']


def test_eof_without_newline_is_forwarded(tmp_path):
    output = tmp_path / 'pandora.log'
    output.write_bytes(b'INFO final line')
    process = Mock()
    process.poll.return_value = 0
    logger, collector = make_logger()
    reader = PandoraOutputReader(str(output), process, logger)

    reader.start()
    reader._thread.join(timeout=1)
    reader.stop()

    assert [record.getMessage() for record in collector.records] == ['INFO final line']


def test_output_written_between_eof_and_exit_is_forwarded(tmp_path):
    output = tmp_path / 'pandora.log'
    output.write_bytes(b'INFO par')
    process = Mock()

    def write_last_lines_and_exit():
        # Pandora дописала вывод и вышла после того, как ридер увидел EOF, но до poll().
        with output.open('ab') as artifact:
            artifact.write(b'tial\nFATAL shutdown failure\n')
        process.poll.side_effect = None
        return 0

    process.poll.side_effect = write_last_lines_and_exit
    process.poll.return_value = 0
    logger, collector = make_logger()
    reader = PandoraOutputReader(str(output), process, logger)

    reader._run()

    assert [record.getMessage() for record in collector.records] == ['INFO partial', 'FATAL shutdown failure']
    assert reader.consumed_offset == output.stat().st_size


def test_truncated_line_does_not_hide_following_line(tmp_path):
    output = tmp_path / 'pandora.log'
    output.write_bytes(b'INFO ' + b'x' * (MAX_EVENT_MESSAGE_BYTES + 20) + b'\nINFO next\n')
    process = Mock()
    process.poll.return_value = 0
    logger, collector = make_logger()
    reader = PandoraOutputReader(str(output), process, logger)

    reader.start()
    reader._thread.join(timeout=1)
    reader.stop()

    messages = [record.getMessage() for record in collector.records]
    assert len(messages) == 2
    assert messages[0] == 'INFO ' + 'x' * (MAX_EVENT_MESSAGE_BYTES - len('INFO '))
    assert messages[1] == 'INFO next'


def test_utf8_split_at_byte_limit_is_replaced(tmp_path):
    output = tmp_path / 'pandora.log'
    output.write_bytes(b'INFO ' + b'x' * (MAX_EVENT_MESSAGE_BYTES - len(b'INFO ') - 1) + '€'.encode('utf-8') + b'\n')
    process = Mock()
    process.poll.return_value = 0
    logger, collector = make_logger()
    reader = PandoraOutputReader(str(output), process, logger)

    reader.start()
    reader._thread.join(timeout=1)
    reader.stop()

    messages = [record.getMessage() for record in collector.records]
    assert len(messages) == 1
    assert messages[0].endswith('\ufffd')
    assert '€' not in messages[0]


def test_read_error_after_forwarded_lines_keeps_unread_suffix(tmp_path):
    output = tmp_path / 'pandora.log'
    processed = b'ERROR sent\nINFO sent\n'
    output.write_bytes(processed + b'FATAL unread\n')
    process = Mock()
    process.poll.return_value = 2
    logger, collector = make_logger()
    reader = PandoraOutputReader(str(output), process, logger)

    class FailingInput(io.BytesIO):
        reads = 0

        def readline(self, size=-1):
            self.reads += 1
            if self.reads == 3:
                raise OSError('simulated read failure')
            return super().readline(size)

    with patch(
        'yandextank.plugins.Pandora.output_log_reader.open',
        return_value=FailingInput(output.read_bytes()),
        create=True,
    ):
        reader.start()
        reader._thread.join(timeout=1)
    reader.stop()

    assert reader.failed
    assert reader.consumed_offset == len(processed)
    assert [record.getMessage() for record in collector.records[:2]] == ['ERROR sent', 'INFO sent']
    assert tail_lines_after(str(output), reader.consumed_offset, 20) == ['FATAL unread']


@pytest.mark.parametrize('level', ['PANIC', 'DPANIC'])
def test_zap_panic_survives_normal_line_budget(tmp_path, level):
    output = tmp_path / 'pandora.log'
    severe_line = f'2026-10-05T12:00:00.000Z\t{level}\tgun.go:42\tfailure'
    output.write_text('INFO noise\n' * 998 + severe_line + '\n')
    process = Mock()
    process.poll.return_value = 1
    logger, collector = make_logger()
    reader = PandoraOutputReader(str(output), process, logger)

    reader.start()
    reader._thread.join(timeout=2)
    reader.stop()

    critical = [record for record in collector.records if record.levelno == logging.CRITICAL]
    assert [record.getMessage() for record in critical] == [severe_line]
