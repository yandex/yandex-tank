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
Handling of sensitive data from environment variables.
"""

from __future__ import annotations

import logging

from collections.abc import Callable
from typing import Any

import attrs

from environ._environ_config import CNF_KEY, RAISE, _ConfigEntry

from ._utils import _get_default_secret, _SecretStr


log = logging.getLogger(__name__)


@attrs.define
class VaultEnvSecrets:
    """
    Loads secrets from environment variables that follow the naming style from
    `envconsul <https://github.com/hashicorp/envconsul>`_.
    """

    vault_prefix: str = attrs.field()

    def secret(
        self,
        default: Any = RAISE,
        converter: Callable | None = None,
        name: str | None = None,
        help: str | None = None,
    ) -> Any:
        """
        Almost identical to `environ.var` except that it takes *envconsul*
        naming into account.
        """
        return attrs.field(
            default=default,
            metadata={
                CNF_KEY: _ConfigEntry(name, default, None, self._get, help)
            },
            converter=converter,
        )

    def _get(self, environ, metadata, prefix, name) -> _SecretStr:
        ce = metadata[CNF_KEY]

        if ce.name is not None:
            var = ce.name
        else:
            if callable(self.vault_prefix):
                vp = self.vault_prefix(environ)
            else:
                vp = self.vault_prefix
            var = "_".join((vp, *prefix[1:], name)).upper()

        log.debug("looking for env var '%s'.", var)
        try:
            val = environ[var]
            return _SecretStr(val)
        except KeyError:
            return _get_default_secret(var, ce.default)
