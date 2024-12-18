from typing import Callable
from ..common import AmmoType, Messages, Message, InlineFormatValidator


class UriInlineValidator(InlineFormatValidator):
    def __init__(self):
        self._msgs = Messages()

    def is_suitable(self, ammo_type: AmmoType) -> bool:
        return ammo_type == AmmoType.URI

    def _check_header(self, header: str):
        result = True
        if not (header.startswith('[') and header.endswith(']')):
            self._msgs.error(Message('Header line must be in square braces'))
            result = False
        if ':' not in header:
            self._msgs.error(Message('Header line does not contain ":"'))
            result = False
        return result

    def _check_field(self, data: dict, field_name: str, value_verifier: Callable[[str], bool]):
        success = 0
        if field_name not in data:
            self._msgs.error(Message(f'No {field_name} in ammo'))
        elif not isinstance(data[field_name], list):
            self._msgs.error(Message(f'{field_name} is not a list'))
        else:
            for value in data[field_name]:
                if not isinstance(value, str) or not value:
                    self._msgs.error(Message(f'{field_name} must be non empty string'))
                elif value_verifier(value):
                    success += 1
        return success

    def validate(self, data: dict) -> Messages:
        messages = Messages()
        success = self._check_field(data, 'uris', lambda uri: True)
        self._check_field(data, 'headers', self._check_header)

        messages.info(Message(f'{success} uris'))
        if not success:
            messages.error(Message('No successful readed packets in ammo'))

        return messages
