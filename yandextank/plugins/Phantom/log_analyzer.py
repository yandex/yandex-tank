import re
from collections import defaultdict
import logging

LOGGER = logging.getLogger(__file__)


class LogFormatError(Exception):
    ...


LINE_FORMAT = r'(\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d.\d\d\d [+-]\d\d\d\d) \[([^\]]+)\] \[([^\]]*)\] (.*)'


class LogLine:
    def __init__(self, line: str):
        mach = re.match(LINE_FORMAT, line)
        if mach is None:
            raise LogFormatError(f"Phantom log line doesn't match format: {LINE_FORMAT}")
        self.time_stamp, self.level, self.name, message = mach.groups()
        self.message = message.strip()


class LogAnalyzer:
    def __init__(self, path):
        self.path = path

    def get_most_recent_errors(self, limit=10):
        counter = defaultdict(int)
        with open(self.path) as f:
            for line in f:
                try:
                    parsed = LogLine(line)
                except LogFormatError:
                    LOGGER.warning('line %s does not recognized as Phantom log')
                    continue
                if parsed.level not in ['error', 'fatal']:
                    continue
                counter[parsed.message] += 1
            return [err for (err, count) in
                    sorted(counter.items(), key=lambda item: -item[1])[:limit]]
