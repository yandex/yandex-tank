from typing import BinaryIO
from ..common import AmmoType, Decision, FileFormatValidator, Features, Messages, Message


class UriValidator(FileFormatValidator):
    def is_suitable(self, features: Features) -> Decision:
        if features.is_begin_of_file_square_braced_lines():
            sline = features.first_non_square_braced_line().split()
            if len(sline) > 0 and sline[0].startswith(b'/'):
                return Decision({AmmoType.URI})
        return Decision(set())

    def _check_header(self, messages: Messages, start_offset: int, header: bytes):
        if b':' not in header:
            messages.error(Message('Header line does not contain ":"', file_offset=start_offset))

    def validate(self, stream: BinaryIO, max_scan_size: int) -> Messages:
        messages = Messages()
        count = 0
        success = 0
        start_offset = stream.tell()
        for line in stream:
            if stream.tell() > max_scan_size:
                break

            line = line.strip(b'\r\n\t ')
            if not line:
                continue
            count += 1

            if line.startswith(b'['):
                if not line.endswith(b']'):
                    messages.error(Message('Header line does not end with "]"', file_offset=start_offset))
                self._check_header(messages, start_offset, line.strip(b'\r\n[]\t '))
            else:
                fields = line.split()
                if len(fields) >= 3:
                    messages.warning(Message('Too many tags. Only one tag is allowed', file_offset=start_offset))
                success += 1

            start_offset = stream.tell()

        messages.info(Message(f'{count} non empty lines read ({success} uris)'))
        if not success:
            messages.error(Message('No successful readed packets in ammo'))

        return messages
