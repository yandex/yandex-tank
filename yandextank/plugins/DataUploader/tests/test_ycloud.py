import pytest
import os
from unittest.mock import patch
from yandextank.plugins.DataUploader.ycloud import load_sa_key, build_sa_key, SAKey, JWTError, AuthTokenProvider
from yandextank.common.util import get_test_path

RAW_KEY_FILE_PATH = os.path.join(get_test_path(), 'yandextank/plugins/DataUploader/tests/test_ycloud/raw_key.txt')
JSON_KEY_FILE_PATH = os.path.join(get_test_path(), 'yandextank/plugins/DataUploader/tests/test_ycloud/json_key.json')


@pytest.fixture()
def patch_get_iam_token_from_metadata():
    with patch('yandextank.plugins.DataUploader.ycloud.get_iam_token_from_metadata') as p:
        p.return_value = ('some_token', 123124123)
        yield p


@pytest.mark.parametrize('file_path, expected', [
    (RAW_KEY_FILE_PATH, SAKey('', '', 'raw_private_key_content')),
    (JSON_KEY_FILE_PATH, SAKey('json service account id', 'json key id', 'json_private_key'))
])
def test_load_sa_key(file_path, expected):
    actual = load_sa_key(file_path)
    assert actual.sa_id == expected.sa_id
    assert actual.key_id == expected.key_id
    assert actual.key == expected.key


@pytest.mark.usefixtures('patch_get_iam_token_from_metadata')
@pytest.mark.parametrize('args', [
    ({}),
    ({'unwanted': 'some_value'}),
])
def test_get_auth_token_requester_metadata(args, patch_get_iam_token_from_metadata):
    _, _ = AuthTokenProvider.get_auth_token_requester(**args)()
    patch_get_iam_token_from_metadata.assert_called_once()


@pytest.mark.parametrize('args, expected', [
    ({'iam_token': 'some_token_payload'}, 'some_token_payload')
])
def test_get_auth_token_requester_iam(args, expected):
    token, _ = AuthTokenProvider.get_auth_token_requester(**args)()
    assert token == expected


@pytest.mark.parametrize('args', [
    ({'sa_key': 'some_private_key', 'sa_id': 'some id'}),
    ({'sa_id': 'some id', 'sa_key_id': 'some key id'}),
    ({'sa_key_file': RAW_KEY_FILE_PATH})
])
def test_get_auth_token_requester_raises_error(args):
    with pytest.raises(JWTError):
        _ = AuthTokenProvider.get_auth_token_requester(**args)


@pytest.mark.parametrize('args, expected', [
    (
        {'sa_key': 'pk', 'sa_id': 'said', 'sa_key_id': 'sakeyid'},
        SAKey('said', 'sakeyid', 'pk')
    ),
    (
        {'sa_key_file': RAW_KEY_FILE_PATH, 'sa_id': 'said', 'sa_key_id': 'sakeyid'},
        SAKey('said', 'sakeyid', 'raw_private_key_content')
    ),
    (
        {'sa_key_file': JSON_KEY_FILE_PATH, 'sa_id': 'said', 'sa_key_id': 'sakeyid'},
        SAKey('said', 'sakeyid', 'json_private_key')
    ),
    (
        {'sa_key_file': JSON_KEY_FILE_PATH},
        SAKey('json service account id', 'json key id', 'json_private_key')
    )
])
def test_build_sa_key(args, expected):
    actual = build_sa_key(**args)

    assert actual.sa_id == expected.sa_id
    assert actual.key_id == expected.key_id
    assert actual.key == expected.key
