import pytest
import unittest.mock as mock

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


@pytest.mark.parametrize(
    'props1, props2, expected_equal',
    [
        ({}, {}, True),
        ({'foo': 'bar'}, {'bar': 'foo'}, True),
        ({'ETag': '1'}, {'ETag': '1'}, True),
        ({'ETag': '1'}, {'ETag': '2'}, False),
        ({'LastModified': '1'}, {'LastModified': '1'}, True),
        ({'LastModified': '1'}, {'LastModified': '2'}, False),
        ({'ETag': '1', 'LastModified': '1'}, {'ETag': '1', 'LastModified': '2'}, True),
    ],
)
def test_s3_opener_accounts_etag(props1, props2, expected_equal):
    url = 's3://bucket/object'
    config = {
        'endpoint_url': 'http://s3.amazonaws.com',
        'aws_access_key_id': '123',
        'aws_secret_access_key': '456',
    }

    opener1 = S3Opener(url, config=config)
    opener2 = S3Opener(url, config=config)

    opener1.conn = mock.Mock()
    opener2.conn = mock.Mock()

    opener1.conn.head_object.return_value = props1
    opener2.conn.head_object.return_value = props2

    file1 = opener1.tmpfile_path()
    file2 = opener2.tmpfile_path()

    if expected_equal:
        assert file1 == file2
    else:
        assert file1 != file2
