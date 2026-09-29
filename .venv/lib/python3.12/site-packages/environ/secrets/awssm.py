# SPDX-License-Identifier: Apache-2.0
#
# Copyright 2021 Chris Rose
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
Handling of sensitive data stored in AWS Secrets Manager
"""

from __future__ import annotations

import logging

from collections.abc import Callable
from typing import Any

import attrs
import boto3

from environ._environ_config import CNF_KEY, RAISE, _ConfigEntry

from ._utils import _get_default_secret


log = logging.getLogger(__name__)


def convert_secret(key):
    def converter(value):
        if isinstance(value, str):
            return value
        return value[key]

    return converter


def _build_secretsmanager_client():
    client = boto3.client("secretsmanager")
    log.debug("Created a secretsmanager client %s", client)
    return client


@attrs.define
class SecretsManagerSecrets:
    """
    Load secrets from the AWS Secrets Manager.

    The secret ID should be stored in the environment variable by name:

    Given this environment::

        export APP_MY_SECRET=prod/db_password
        export APP_A_DIFFERENT_NAME=prod/api_key

    And this app::

        sm = SecretsManagerSecrets()

        @environ.config
        class Cfg:
            my_secret = sm.secret()
            my_aliased_secret = sm.secret(name="A_DIFFERENT_NAME")

    Then the secrets will be looked up in AWS Secrets Manager with the Secret
    IDs ``prod/db_password`` and ``prod/api_key``, respectively.

    .. warning::

       Requires `boto3 <https://pypi.org/project/boto3/>`_! Please install
       *environ-config* with the ``aws`` extra: ``python -Im pip install
       environ-config[aws]``

    .. versionadded:: 21.4.0
    """

    _client: boto3.client | None = None

    @property
    def client(self) -> boto3.client:
        if self._client is None:
            self._client = _build_secretsmanager_client()

        return self._client

    def secret(
        self,
        default: Any = RAISE,
        converter: Callable = convert_secret("SecretString"),  # noqa: B008
        name: str | None = None,
        help: str | None = None,
    ):
        """
        Declare a secrets manager secret on an `environ.config`-decorated class

        All parameters work just like in `environ.var`.

        .. note::

            By default, a converter is set that will extract the
            ``SecretString`` field from the
            ``SecretsManager.Client.get_secret_value()`` response for you. If
            you wish you convert the value yourself and therefore overwrite the
            converter, you must take this into account and grab
            ``SecretString`` (or ``SecretBinary``) yourself.
        """
        return attrs.field(
            default=default,
            metadata={
                CNF_KEY: _ConfigEntry(name, default, None, self._get, help)
            },
            converter=converter,
        )

    def _get(self, environ, metadata, prefix, name):
        ce = metadata[CNF_KEY]
        if ce.name:
            secret_name_envvar = ce.name
            log.debug(
                "override env variable with explicit name %s",
                secret_name_envvar,
            )
        else:
            parts = (*prefix, name)
            secret_name_envvar = "_".join(parts).upper()
            log.debug(
                "secret name environment variable %s", secret_name_envvar
            )

        try:
            secret_name = environ[secret_name_envvar]
        except KeyError:
            # missing the environment; let's try to get the default
            log.debug(
                "no key %s in environment, using default=%s",
                secret_name_envvar,
                ce.default,
            )
            return _get_default_secret(secret_name_envvar, ce.default)
        log.debug("secret name: %s", secret_name)

        return self.client.get_secret_value(SecretId=secret_name)
