import pytest

from yandextank.contrib.netort.netort.resource import (
    FileOpener,
    HttpOpener,
    open_file,
    ResourceManager,
    ResourceManagerConfig,
    S3Opener,
)


@pytest.mark.parametrize(
    'filename, expected_opener',
    [
        ('/home/user/ammo.file', FileOpener),
        ('https://some-proxy-for-ammo/12345678', HttpOpener),
        ('s3://test-data/request.ammo', S3Opener),
    ],
)
def test_get_correct_opener(filename, expected_opener, patch_resource_manager):
    rm = ResourceManager(ResourceManagerConfig())
    opener = rm.get_opener(filename)
    assert isinstance(opener, expected_opener)


@pytest.mark.parametrize(
    'filename, opener_args',
    [
        ('/home/user/ammo.file', []),
        ('https://some-proxy-for-ammo/12345678', [True]),
        ('s3://test-data/request.ammo', [True]),
    ],
)
def test_open_file_with_opener(filename, opener_args, patch_resource_manager):
    rm = ResourceManager(ResourceManagerConfig())
    opener = rm.get_opener(filename)
    with open_file(opener, use_cache=True):
        pass
    opener.open.assert_called_once_with(*opener_args)
