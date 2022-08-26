import tempfile
import pytest
from pathlib import Path

from yandextank.plugins.Phantom.log_analyzer import LogAnalyzer, LogLine

LOG_SAMPLE = """2022-03-18 19:08:11.525 +0300 [error] [benchmark_io 4639] socket: Too many open files
2022-03-18 19:08:11.525 +0300 [error] [benchmark_io 4625] socket: Too many open files
2022-03-18 19:08:11.526 +0300 [error] [benchmark_io 4643] socket: Too many open files
2022-03-18 19:08:11.526 +0300 [error] [benchmark_io 4658] socket: Too many open files
2022-03-18 19:08:11.526 +0300 [error] [benchmark_io 4644] socket: Too many open files
2022-03-18 19:08:11.583 +0300 [error] [monitor_io] bq_sleep: Operation canceled
2022-03-18 19:08:11.584 +0300 [error] [benchmark_io stream_method brief_logger] bq_sleep: Operation canceled
2022-03-18 19:08:11.584 +0300 [error] [benchmark_io] cond-wait: Operation canceled
2022-03-18 19:08:11.584 +0300 [error] [monitor_io] bq_sleep: Operation canceled
2022-03-18 19:08:11.601 +0300 [error] [phantom_logger] bq_sleep: Operation canceled
2022-03-18 19:08:11.609 +0300 [info] [] Exit"""


def test_one_most_recent_error():
    with tempfile.NamedTemporaryFile() as file:
        Path(file.name).write_text(LOG_SAMPLE)
        (error,) = LogAnalyzer(file.name).get_most_recent_errors(1)
    assert 'socket: Too many open files' == error


def test_most_recent_errors():
    with tempfile.NamedTemporaryFile() as file:
        Path(file.name).write_text(LOG_SAMPLE)
        errors = LogAnalyzer(file.name).get_most_recent_errors()
    assert ['socket: Too many open files',
            'bq_sleep: Operation canceled',
            'cond-wait: Operation canceled',
            ] == errors


def test_empty_errors():
    with tempfile.NamedTemporaryFile() as file:
        Path(file.name).write_text('')
        errors = LogAnalyzer(file.name).get_most_recent_errors()
    assert [] == errors


@pytest.mark.parametrize(('line', 'level', 'message'), [
    ('2022-03-18 19:08:11.525 +0300 [error] [benchmark_io 4639] socket: Too many open files',
     'error',
     'socket: Too many open files',
     ),
    ('2022-03-18 19:08:11.584 +0300 [error] [benchmark_io stream_method brief_logger] bq_sleep: Operation canceled',
     'error',
     'bq_sleep: Operation canceled',
     ),
    ('2022-03-18 19:08:11.609 +0300 [info] [] Exit',
     'info',
     'Exit',
     ),
])
def test_line_split(line, level, message):
    parsed = LogLine(line)
    assert level == parsed.level
    assert message == parsed.message
