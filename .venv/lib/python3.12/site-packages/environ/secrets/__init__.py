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
Handling of sensitive data.
"""

from environ.exceptions import MissingSecretImplementationError

from ._dir import DirectorySecrets
from ._ini import INISecrets
from ._vault import VaultEnvSecrets


try:
    from environ.secrets.awssm import SecretsManagerSecrets
except ImportError:  # pragma: no cover

    class SecretsManagerSecrets:
        def secret(self, *args, **kwargs):
            msg = "AWS secrets manager requires boto3"
            raise MissingSecretImplementationError(msg)


__all__ = [
    "DirectorySecrets",
    "INISecrets",
    "SecretsManagerSecrets",
    "VaultEnvSecrets",
]
