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
Handling of sensitive data from directories.
"""

from __future__ import annotations

import logging

from collections.abc import Callable
from pathlib import Path
from typing import Any

import attrs

from environ._environ_config import CNF_KEY, RAISE, _ConfigEntry

from ._utils import _get_default_secret, _SecretStr


log = logging.getLogger(__name__)


FileOpenError = OSError


@attrs.define
class DirectorySecrets:
    """
    Load secrets from a directory containing secrets in separate files.
    Suitable for reading Docker or Kubernetes secrets from the filesystem
    inside a container.

    .. versionadded:: 21.1.0
    """

    secrets_dir: str | Path = attrs.field()
    _env_name: str | None = attrs.field(default=None)

    @classmethod
    def from_path(cls, path: str | Path) -> DirectorySecrets:
        """
        Look for secrets in *path* directory.

        Args:
            path: A path to directory containing secrets as files.
        """
        return cls(path)

    @classmethod
    def from_path_in_env(
        cls, env_name: str, default: str | Path | None
    ) -> DirectorySecrets:
        """
        Get the path from the environment variable *env_name* and then load the
        secrets from that directory at runtime.

        This allows you to overwrite the path to the secrets directory in
        development.

        Args:
            env_name:
                Environment variable that is used to determine the path of the
                secrets directory.

            default: The default path to load from.
        """
        return cls(default, env_name)

    def secret(
        self,
        default: Any = RAISE,
        converter: Callable | None = None,
        name: str | None = None,
        help: str | None = None,
    ) -> Any:
        return attrs.field(
            default=default,
            metadata={
                CNF_KEY: _ConfigEntry(name, default, None, self._get, help)
            },
            converter=converter,
        )

    def _get(self, environ, metadata, prefix, name) -> _SecretStr:
        ce = metadata[CNF_KEY]
        # conventions for file naming might be different
        # than for environment variables, so we don't call .upper()
        filename = ce.name or "_".join((*prefix[1:], name))

        # Looking up None in os.environ is an error.
        if self._env_name:
            secrets_dir = environ.get(self._env_name, self.secrets_dir)
        else:
            secrets_dir = self.secrets_dir

        secret_path = Path(secrets_dir) / filename
        log.debug("looking for secret in file '%s'.", secret_path)

        try:
            return _SecretStr(secret_path.read_text())
        except FileOpenError:
            return _get_default_secret(filename, ce.default)
