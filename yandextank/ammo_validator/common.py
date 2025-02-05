#!/usr/bin/env python
from collections import defaultdict
from dataclasses import dataclass
import json
from enum import StrEnum, auto
import logging
from typing import BinaryIO, ClassVar, NewType, Protocol, runtime_checkable

from yandextank.contrib.netort.netort.resource import ResourceManager, open_file


class AmmoType(StrEnum):
    UNSPECIFIED = auto()
    RAW = 'raw'
    URI = 'uri'
    URIPOST = 'uripost'
    PHANTOM = 'phantom'
    HTTP_JSON = 'http/json'
    GRPC_JSON = 'grpc/json'


Decision = NewType('Decision', set[AmmoType])


class Features:
    def __init__(self) -> None:
        self._first_line = None

        self._is_first_line_json = False
        self._first_line_json = None

        self._is_begin_of_file_square_braced_lines = False
        self._first_non_square_braced_line = None

    @staticmethod
    def from_file(resource_manager: ResourceManager, ammo_file: str, max_scan_size: int, use_cache=True) -> 'Features':
        features = Features()
        features.parse(resource_manager, ammo_file, max_scan_size, use_cache)
        return features

    def parse(self, resource_manager: ResourceManager, ammo_file: str, max_scan_size: int, use_cache=True) -> None:
        searching_first_line = True
        searching_first_non_braced = True

        opener = resource_manager.get_opener(ammo_file)
        with open_file(opener, use_cache) as stream:
            while stream.tell() < max_scan_size and (searching_first_line or searching_first_non_braced):
                try:
                    line = next(stream)
                    line = line.rstrip(b'\r\n')
                except StopIteration:
                    break

                if searching_first_line:
                    self._first_line = line
                    if line.startswith(b'{'):
                        try:
                            self._first_line_json = json.loads(line.decode('utf-8'))
                            self._is_first_line_json = True
                        except json.JSONDecodeError:
                            pass
                    searching_first_line = False

                if searching_first_non_braced:
                    if line.startswith(b'[') and line.endswith(b']'):
                        self._is_begin_of_file_square_braced_lines = True
                    else:
                        if self._is_begin_of_file_square_braced_lines:
                            self._first_non_square_braced_line = line
                        searching_first_non_braced = False

    def first_line(self) -> bytes:
        assert self._first_line is not None
        return self._first_line

    def is_first_line_json(self) -> bool:
        return self._is_first_line_json

    def first_line_json(self) -> dict:
        assert self._first_line_json is not None
        return self._first_line_json

    def is_begin_of_file_square_braced_lines(self) -> bool:
        return self._is_begin_of_file_square_braced_lines

    def first_non_square_braced_line(self) -> bytes:
        assert self._first_non_square_braced_line is not None
        return self._first_non_square_braced_line


@dataclass
class Message:
    msg: str
    ammo_file: str = ''
    file_offset: int = -1
    validator_name: str = ''

    def replace(self, ammo_file: str | None = None) -> "Message":
        return Message(
            msg=self.msg,
            ammo_file=ammo_file if ammo_file is not None else self.ammo_file,
            file_offset=self.file_offset,
            validator_name=self.validator_name,
        )


class Messages:
    infos: list[Message]
    warnings: list[Message]
    errors: list[Message]

    def __init__(self):
        self.infos = []
        self.warnings = []
        self.errors = []

    def info(self, msg: Message):
        self.infos.append(msg)

    def warning(self, msg: Message):
        self.warnings.append(msg)

    def error(self, msg: Message):
        self.errors.append(msg)

    def update(self, other: "Messages", /, ammo_file: str | None = None):
        self.infos.extend(m.replace(ammo_file=ammo_file) for m in other.infos)
        self.warnings.extend(m.replace(ammo_file=ammo_file) for m in other.warnings)
        self.errors.extend(m.replace(ammo_file=ammo_file) for m in other.errors)

    def summarize(self, logger: logging.Logger, max_messages_sequence: int = 20):
        all_msgs: defaultdict[
            str,
            defaultdict[str, tuple[defaultdict[str, set[int]], defaultdict[str, set[int]], defaultdict[str, set[int]]]],
        ] = defaultdict(lambda: defaultdict(lambda: (defaultdict(set), defaultdict(set), defaultdict(set))))
        for msg in self.infos:
            all_msgs[msg.ammo_file][msg.validator_name][0][msg.msg].add(msg.file_offset)
        for msg in self.warnings:
            all_msgs[msg.ammo_file][msg.validator_name][1][msg.msg].add(msg.file_offset)
        for msg in self.errors:
            all_msgs[msg.ammo_file][msg.validator_name][2][msg.msg].add(msg.file_offset)
        for ammo_file, ammo_msgs in all_msgs.items():
            for validator_name, validator_msgs in ammo_msgs.items():
                if not validator_msgs[0] and not validator_msgs[1] and not validator_msgs[2]:
                    continue
                title_printed = False
                for msgs, report_func in [
                    (validator_msgs[2], logger.error),
                    (validator_msgs[1], logger.warning),
                    (validator_msgs[0], logger.info),
                ]:
                    if msgs and not title_printed:
                        if ammo_file:
                            report_func(f'Ammo file {ammo_file}.')
                        if validator_name:
                            report_func(f'Validator {validator_name}.')
                        title_printed = True

                    for msg, offsets in msgs.items():
                        report_msg = ['  ']
                        report_msg.append(msg if msg.endswith('.') else f'{msg}.')
                        if offsets != {-1}:
                            offsets_str = ",".join(str(o) for o in sorted(offsets)[:max_messages_sequence])
                            if len(offsets) > max_messages_sequence:
                                report_msg.append(
                                    f'Happend {len(offsets)} times. First {max_messages_sequence} offsets: {offsets_str}.'
                                )
                            else:
                                report_msg.append(f'Offsets {offsets_str}.')
                        report_func(' '.join(report_msg))

    def brief(self) -> str:
        if not self.infos and not self.warnings and not self.errors:
            return ''
        msg = [
            'Total '
            + ', '.join(
                f'{len(messages)} {name}'
                for name, messages in (('infos', self.infos), ('warnings', self.warnings), ('errors', self.errors))
            )
        ]
        for name, messages in (('errors', self.errors), ('warnings', self.warnings)):
            if messages:
                msg.append(f'First {name}:')
                # sort that first is more general messages - w/o validator_name and file_offset
                messages = sorted(
                    messages, key=lambda m: (1 if m.validator_name else 0) + (1 if m.file_offset >= 0 else 0)
                )
                for m in messages[:3]:
                    msg.append(f'  {m.msg}')
                break
        return '\n'.join(msg)


@runtime_checkable
class FileFormatValidator(Protocol):
    AMMO_TYPES: ClassVar[set[AmmoType]]

    def is_suitable(self, features: Features) -> Decision: ...

    def validate(self, stream: BinaryIO, max_scan_size: int) -> Messages: ...

    def _msg(self, msg: str, file_offset: int = -1) -> Message:
        return Message(msg, file_offset=file_offset, validator_name=self.__class__.__name__)


@runtime_checkable
class InlineFormatValidator(Protocol):
    def is_suitable(self, ammo_type: AmmoType) -> bool: ...

    def validate(self, data: dict) -> Messages: ...

    def _msg(self, msg: str, file_offset: int = -1) -> Message:
        return Message(msg, file_offset=file_offset, validator_name=self.__class__.__name__)
