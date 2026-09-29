# SPDX-License-Identifier: Apache-2.0
#
# Copyright 2017 Hynek Schlawack
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys

from configparser import RawConfigParser
from pathlib import Path

import attrs

from .._environ_config import Raise
from ..exceptions import MissingSecretError


def _get_default_secret(var, default):
    """
    Get default or raise MissingSecretError.
    """
    if isinstance(default, attrs.Factory):
        return attrs.NOTHING

    if isinstance(default, Raise):
        raise MissingSecretError(var)

    return default


def _load_ini(path: str) -> RawConfigParser:
    """
    Load an INI file from *path*.
    """
    cfg = RawConfigParser()
    with Path(path).open() as f:
        cfg.read_file(f)

    return cfg


class _SecretStr(str):
    """
    String that censors its __repr__ if called from an attrs repr.
    """

    __slots__ = ()

    def __repr__(self) -> str:
        # The frame numbers varies across attrs versions. Use this convoluted
        # form to make the call lazy.
        if (
            sys._getframe(1).f_code.co_name == "__repr__"
            or sys._getframe(2).f_code.co_name == "__repr__"
        ):
            return "<SECRET>"

        return str.__repr__(self)
