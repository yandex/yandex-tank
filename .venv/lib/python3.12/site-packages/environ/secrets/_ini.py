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

"""
Handling of sensitive data from INI files.
"""

from __future__ import annotations

import logging

from collections.abc import Callable
from configparser import NoOptionError, RawConfigParser
from pathlib import Path
from typing import Any

import attrs

from environ._environ_config import CNF_KEY, RAISE, _ConfigEntry

from ._utils import _get_default_secret, _load_ini, _SecretStr


log = logging.getLogger(__name__)


FileOpenError = OSError


@attrs.define
class INISecrets:
    """
    Load secrets from an `INI file <https://en.wikipedia.org/wiki/INI_file>`_
    using `configparser.RawConfigParser`.
    """

    section: str = attrs.field()
    _cfg: RawConfigParser = attrs.field(default=None)
    _env_name: str | None = attrs.field(default=None)
    _env_default: Any = attrs.field(default=None)

    @classmethod
    def from_path(cls, path: str | Path, section="secrets") -> INISecrets:
        """
        Look for secrets in *section* of *path*.

        Args:
            path: A path to an INI file.

            section: The section in the INI file to read the secrets from.
        """
        return cls(section, _load_ini(str(path)), None, None)

    @classmethod
    def from_path_in_env(
        cls,
        env_name: str,
        default: str | None = None,
        section: str = "secrets",
    ) -> INISecrets:
        """
        Get the path from the environment variable *env_name* **at runtime**
        and then load the secrets from it.

        This allows you to overwrite the path to the secrets file in
        development.

        Args:
            env_name:
                Environment variable that is used to determine the path of the
                secrets file.

            default: The default path to load from.

            section: The section in the INI file to read the secrets from.
        """
        return cls(section, None, env_name, default)

    def secret(
        self,
        default: Any = RAISE,
        converter: Callable | None = None,
        name: str | None = None,
        section: str | None = None,
        help: str | None = None,
    ) -> Any:
        """
        Declare a secret on an `environ.config`-decorated class.

        Args:
            section: Overwrite the section where to look for the values.

        Other parameters work just like in `environ.var`.
        """
        if section is None:
            section = self.section

        return attrs.field(
            default=default,
            metadata={
                CNF_KEY: _ConfigEntry(name, default, None, self._get, help),
                CNF_INI_SECRET_KEY: _INIConfig(section),
            },
            converter=converter,
        )

    def _get(self, environ, metadata, prefix, name) -> _SecretStr:
        # Delayed loading.
        if self._cfg is None and self._env_name is not None:
            log.debug("looking for env var '%s'.", self._env_name)
            self._cfg = _load_ini(
                environ.get(self._env_name, self._env_default)
            )

        ce = metadata[CNF_KEY]
        ic = metadata[CNF_INI_SECRET_KEY]
        section = ic.section

        var = ce.name if ce.name is not None else "_".join((*prefix[1:], name))
        try:
            log.debug("looking for '%s' in section '%s'.", var, section)
            val = self._cfg.get(section, var)

            return _SecretStr(val)
        except NoOptionError:
            return _get_default_secret(var, ce.default)


CNF_INI_SECRET_KEY = CNF_KEY + "_ini_secret"


@attrs.define
class _INIConfig:
    section: str = attrs.field()
