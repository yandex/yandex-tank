import pytest
from unittest.mock import patch

from yandextank.contrib.netort.netort.resource import (
    FileOpener,
    HttpOpener,
    ResourceManager,
    S3Opener,
)


@pytest.fixture
def patch_file_opener():
    with patch.object(FileOpener, 'open') as p:
        yield p


@pytest.fixture
def patch_http_opener():
    with patch.object(HttpOpener, 'open'):
        with patch.object(HttpOpener, 'get_request_info') as p:
            yield p


@pytest.fixture
def patch_s3_opener():
    with patch.object(S3Opener, 'open') as p:
        yield p


@pytest.fixture
def patch_resource_manager(patch_s3_opener, patch_http_opener, patch_file_opener):
    with patch.object(ResourceManager, 'load_config_safe') as p:
        p.load_config_safe.return_value = {}
        yield p
