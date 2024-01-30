import pytest
from yandextank.contrib.netort.netort.data_manager.common.condition import uri_like, path_like, and_


@pytest.mark.parametrize(
    'uri, expected',
    [
        ('http://website.com', True),
        ('https://website.com/55473443', True),
        ('https://website.com/55473443?param1=v1&param2=v2', True),
        ('http://website.com:8080', True),
        ('http://website.com:433', True),
        ('http://website.com:433', True),
        ('http://website.com:12#hashtag', True),
        ('http://other-host.yandex-team.ru', False),
        ('https://other-host.yandex-team.ru:443', False),
        ('s3://other-host.yandex-team.ru', False),
        ('s3://website.com', True),
        ('website.com', False),
        ('website.com/55473443', False),
    ],
)
def test_condition_uri_like_host(uri, expected):
    condition = uri_like(host='website.com')
    assert condition(uri) == expected


@pytest.mark.parametrize(
    'uri, expected',
    [
        ('http://sd.website.com', True),
        ('https://anothersd.website.com/55473443', True),
        ('https://notsamewebsite.com/', False),
    ],
)
def test_condition_uri_like_host_subdomain(uri, expected):
    condition = uri_like(host='*.website.com')
    assert condition(uri) == expected


@pytest.mark.parametrize(
    'uri, scheme, expected',
    [
        ('http://website.com', 'http', True),
        ('https://website.com/55473443', 'http', False),
        ('https://website.com/55473443?param1=v1&param2=v2', 'https', True),
        ('s3://other-host.yandex-team.ru', 's3',  True),
        ('s3://other-host.yandex-team.ru', 'http',  False),
        ('file:///some/abcpath', 'file', True),
        ('file://~/some/relpath', 'file', True),
        ('~/some/relpath', '', True),
        ('other-host.yandex-team.ru', '', True),
        ('customschema://~/some/relpath', 'customschema', True),
        ('customschema://~/some/relpath', 'file', False),
    ],
)
def test_condition_uri_like_scheme(uri, scheme, expected):
    condition = uri_like(scheme=scheme)
    assert condition(uri) == expected


@pytest.mark.parametrize(
    'uri, scheme, host, path, expected',
    [
        ('http://website.com', 'http', 'website.com', None, True),
        ('http://website.com/path?asdf', 'http', 'website.com', '/path', True),
        ('https://website.com/otherPath', None, 'website.com', '/otherPath', True),
        ('https://website.com/caseInsensitivePath?queryP=1', None, 'website.com', '/caseinsensitivepath', True),
        ('http://website.com/path?asdf', 'http', None, '/path', True),
        ('http://other.website.com/path?asdf', 'http', None, '/path', True),
        ('http://other.website.com/path?asdf', 'http', None, '', False),
        ('http://other.website.com/?asdf', 'http', None, '/', True),
        ('http://website.com', 'http', 'website.com', None, True),
        ('http://website.com', 'http', 'website.com', None, True),
    ],
)
def test_condition_uri_like(uri, scheme, host, path, expected):
    condition = uri_like(scheme=scheme, host=host, path=path)
    assert condition(uri) == expected


@pytest.mark.parametrize(
    'pattern, path, expected',
    [
        ('/*', '/dev/segment/', True),
        ('/*/segment/', '/dev/segment/', True),
        ('/', '/dev/segment/', False),
        ('/caseSensitive/*', '/caseSensitive/', True),
        ('/caseSensitive/*', '/casesensitive/', False),
    ],
)
def test_condition_path_like(pattern, path, expected):
    condition = path_like(pattern)
    assert condition(path) == expected


def test_condition_and():
    for c1 in [True, False]:
        for c2 in [True, False]:
            for c3 in [True, False]:
                expected = c1 and c2 and c3
                assert expected == and_(lambda _: c1, lambda *args: c2, lambda uri: c3)('')
