import json
from typing import BinaryIO
from ..common import AmmoType, Decision, FileFormatValidator, Features, Messages, Message


class JsonHttpValidator(FileFormatValidator):
    def is_suitable(self, features: Features) -> Decision:
        if features.is_first_line_json():
            doc = features.first_line_json()
            if doc.get('uri'):
                return Decision({AmmoType.HTTP_JSON})
        return Decision(set())

    def _check_field(
        self, messages: Messages, line_start_offset: int, doc: dict, field_name: str, field_type, required: bool
    ):
        if field_name not in doc:
            if required:
                messages.error(Message(f'"{field_name}" field required', file_offset=line_start_offset))
        else:
            if field_type is not None and not isinstance(doc[field_name], field_type):
                messages.error(
                    Message(f'"{field_name}" field must be {field_type.__name__}', file_offset=line_start_offset)
                )

    def _check_headers(self, messages: Messages, line_start_offset: int, doc: dict):
        if 'headers' in doc:
            if not isinstance(doc['headers'], dict):
                messages.error(Message('"headers" field must be object', file_offset=line_start_offset))
            else:
                for key, value in doc['headers'].items():
                    if not isinstance(key, str) or not isinstance(value, str):
                        messages.error(
                            Message(
                                '"headers" field must be object with string keys and string values',
                                file_offset=line_start_offset,
                            )
                        )

    def _check_body(self, messages, line_start_offset, doc):
        if 'body' not in doc:
            messages.error(Message('"body" field required', file_offset=line_start_offset))

    def validate(self, stream: BinaryIO, max_scan_size: int) -> Messages:
        messages = Messages()
        count = 0
        success = 0
        line_start_offset = stream.tell()
        for line in stream:
            line = line.strip(b'\r\n\t ')
            if not line:
                continue
            count += 1

            try:
                doc = json.loads(line.decode())
            except UnicodeDecodeError:
                messages.error(Message('Invalid json line - not in utf-8', file_offset=line_start_offset))
                continue
            except json.JSONDecodeError:
                messages.error(Message('Error at parse line as JSON', file_offset=line_start_offset))
                continue

            if not isinstance(doc, dict):
                messages.error(Message('Top level of JSON must be object', file_offset=line_start_offset))
                continue

            n_errors_before = len(messages.errors)
            self._check_field(messages, line_start_offset, doc, 'host', str, True)
            self._check_field(messages, line_start_offset, doc, 'method', str, True)
            self._check_field(messages, line_start_offset, doc, 'uri', str, True)
            self._check_field(messages, line_start_offset, doc, 'tag', str, False)
            self._check_field(messages, line_start_offset, doc, 'body', None, False)
            self._check_headers(messages, line_start_offset, doc)

            if n_errors_before == len(messages.errors):
                success += 1

            line_start_offset = stream.tell()
            if line_start_offset > max_scan_size:
                break

        messages.info(Message(f'{count} non empty lines read. {success} packets seems good'))
        if not success:
            messages.error(Message('No successful readed packets in ammo'))
        return messages
