from typing import BinaryIO
from ..common import AmmoType, Decision, FileFormatValidator, Features, Messages, Message


KNOWN_HTTP_REQUEST_METHODS = {'GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'CONNECT', 'OPTIONS', 'TRACE', 'PATCH'}


class PhantomValidator(FileFormatValidator):
    def __init__(self):
        self._has_crlf_between_packets = True
        self._msgs = Messages()

    def is_suitable(self, features: Features) -> Decision:
        try:
            sline = features.first_line().strip().split()
            if sline and int(sline[0].decode()) > 0:
                return Decision({AmmoType.PHANTOM, AmmoType.RAW})
        except Exception:
            pass
        return Decision(set())

    def _read_packet_first_line(self, stream: BinaryIO, packet_start_offset: int) -> int | None:
        while True:
            size_bytes = stream.readline(65536)
            if not size_bytes:
                return None
            if not size_bytes.endswith(b"\n"):
                self._msgs.error(Message("Invalid packet header - too long line", file_offset=packet_start_offset))

            try:
                size_str = size_bytes.decode().strip()
            except UnicodeDecodeError:
                self._msgs.error(Message("Invalid packet header - not in utf-8", file_offset=packet_start_offset))
                return None

            size_tag = size_str.split()
            if len(size_tag) == 0:
                self._has_crlf_between_packets = True
                continue
            if len(size_tag) > 2:
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

    def _split_http_packet(self, data: bytes, packet_start_offset: int) -> tuple[str, dict[str, str], bytes]:
        header_end_offset = data.find(b"\r\n\r\n")
        if header_end_offset < 0:
            self._msgs.error(Message("Invalid HTTP header - no CRLFCRLF", file_offset=packet_start_offset))
            return '', {}, data

        http_request = ''
        packet_header = {}
        for header_idx, header_str in enumerate(data[: header_end_offset + 2].decode().split("\n")):
            if header_idx == 0:
                http_request = header_str.strip()
                continue
            if not header_str:
                break
            if header_str.endswith("\r"):
                header_str = header_str[:-1]
            else:
                self._msgs.warning(
                    Message(
                        f"Invalid HTTP header - string not ends with \\r: {header_str[:20]}",
                        file_offset=packet_start_offset,
                    )
                )
            header_parts = header_str.split(": ", maxsplit=1)
            if len(header_parts) != 2:
                self._msgs.warning(
                    Message(
                        f"Invalid HTTP header - can't split to key and value: {header_str[:20]}",
                        file_offset=packet_start_offset,
                    )
                )
            packet_header[header_parts[0]] = header_parts[1]
        return http_request, packet_header, data[header_end_offset + 4 :]

    def _check_http_request(self, request: str, packet_start_offset: int):
        request_items = request.split()
        if len(request_items) != 3:
            self._msgs.warning(Message("Invalid HTTP request - not 3 parts", file_offset=packet_start_offset))
        else:
            if request_items[0] not in KNOWN_HTTP_REQUEST_METHODS:
                self._msgs.warning(
                    Message("Invalid HTTP request - unknown request method", file_offset=packet_start_offset)
                )
            if not request_items[2].startswith('HTTP/'):
                self._msgs.warning(
                    Message("Invalid HTTP request - protocol not starts with HTTP/", file_offset=packet_start_offset)
                )

    def _check_http_headers(self, headers: dict[str, str], body: bytes, packet_start_offset: int):
        if "Content-Length" in headers:
            header_content_length = int(headers["Content-Length"])
            body_length = len(body)
            if body_length != header_content_length:
                if body_length > header_content_length:
                    msg = "Invalid HTTP header - body size is bigger than Content-Length"
                else:
                    msg = "Invalid HTTP header - Content-Length is greater than real body length"
                self._msgs.error(Message(msg, file_offset=packet_start_offset))

    def validate(self, stream: BinaryIO, max_scan_size: int) -> Messages:
        # <byte_length> [tag]\n<request>\r\n<request_headers>\r\n\r\n[request_body][\n[\n]]
        # byte_length fits next block: <request>\r\n<request_headers>\r\n\r\n[request_body]
        count = 0
        success = 0

        while True:
            packet_start_offset = stream.tell()
            if max_scan_size and packet_start_offset > max_scan_size:
                break

            size = self._read_packet_first_line(stream, packet_start_offset)
            if size is None:
                break
            if size == 0:
                continue

            count += 1

            packet_data = stream.read(size)
            if len(packet_data) != size:
                self._msgs.error(
                    Message(
                        f"Invalid size (read {len(packet_data)} bytes, expected {size} bytes)",
                        file_offset=packet_start_offset,
                    )
                )

            request, headers, body = self._split_http_packet(packet_data, packet_start_offset)
            if request or headers:
                self._check_http_request(request, packet_start_offset)
                self._check_http_headers(headers, body, packet_start_offset)

                success += 1

        self._msgs.info(Message(f'{count} packets read ({success} successes)'))
        if not success:
            self._msgs.error(Message('No successful readed packets in ammo'))
        if not self._has_crlf_between_packets:
            self._msgs.info(Message('It is recomended add CRLF between packets for better readibility by human'))
        return self._msgs
