from typing import BinaryIO
from ..common import AmmoType, Decision, FileFormatValidator, Features, Messages, Message


class UriPostValidator(FileFormatValidator):
    def __init__(self):
        self._msgs = Messages()

    def is_suitable(self, features: Features) -> Decision:
        if features.is_begin_of_file_square_braced_lines() and features.first_non_square_braced_line():
            sline = features.first_non_square_braced_line().split()
            if len(sline) >= 2 and sline[1].startswith(b'/'):
                try:
                    int(sline[0].decode())
                    return Decision({AmmoType.URIPOST})
                except ValueError:
                    pass
        return Decision(set())

    def _check_header(self, start_offset: int, header: str):
        if ':' not in header:
            self._msgs.error(Message('Header line does not contain ":"', file_offset=start_offset))

    def _read_packet_begin(self, stream: BinaryIO, packet_start_offset: int) -> int | None:
        headers = []
        while True:
            line_bytes = stream.readline(65536)
            if not line_bytes:
                return None
            if not line_bytes.endswith(b"\n"):
                self._msgs.error(Message("Invalid packet header - too long line", file_offset=packet_start_offset))

            try:
                line_str = line_bytes.decode().strip()
            except UnicodeDecodeError:
                self._msgs.error(Message("Invalid packet header - not in utf-8", file_offset=packet_start_offset))
                return None

            if line_str.startswith('['):
                if not line_str.endswith(']'):
                    self._msgs.error(Message("Invalid packet header - missing ']'", file_offset=packet_start_offset))
                line_str = line_str.strip('[]\r\n\t ')
                self._check_header(packet_start_offset, line_str)
                headers.append(line_str)
                continue

            size_tag = line_str.split()
            if len(size_tag) == 0:
                continue
            if len(size_tag) > 3:
                self._msgs.error(Message("Invalid packet header - too many tags", file_offset=packet_start_offset))

            try:
                size = int(size_tag[0])
            except ValueError:
                self._msgs.error(Message('Packet size not a number', file_offset=packet_start_offset))
                return None
            if size < 0:
                self._msgs.error(Message('Packet size must be positive integer', file_offset=packet_start_offset))
                return None
            if size > 0:
                return size

    def validate(self, stream: BinaryIO, max_scan_size: int) -> Messages:
        count = 0
        success = 0

        packet_start_offset = stream.tell()
        while not max_scan_size or packet_start_offset < max_scan_size:
            packet_start_offset = stream.tell()
            size = self._read_packet_begin(stream, packet_start_offset)
            if size is None:
                break
            if size == 0:
                continue

            count += 1

            packet_data = stream.read(size)
            if len(packet_data) != size:
                self._msgs.error(Message("Invalid size of packet data", file_offset=packet_start_offset))
                continue

            success += 1

        self._msgs.info(Message(f'{count} packets read ({success} successes)'))
        if not success:
            self._msgs.error(Message('No successful readed packets in ammo'))
        return self._msgs
