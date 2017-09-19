import pytest
from yandextank.validator.docs_gen import RSTFormatter, TextBlock

@pytest.mark.parametrize('s1, s2, expected', [
    ('type: list\nelements:\n\ttype: string',
     'type: string\nallowed: auto\ndescription:',
     """+--------------------------------+
|             any of             |
+================+===============+
| type: list     | type: string  |
| elements:      | allowed: auto |
|   type: string | description:  |
+----------------+---------------+"""
     )
])
def test_any_of(s1, s2, expected):
    assert RSTFormatter.any_of([TextBlock(s1), TextBlock(s2)]) == expected


@pytest.mark.parametrize('s, expected',[
    ('type: list\nelements:\n\ttype: string', '| type: list\n| elements:\n|   type: string'),
    ('type: string\nallowed: auto\ndescription:', '| type: string\n| allowed: auto\n| description:')
])
def test_preserve_indents(s, expected):
    assert RSTFormatter.preserve_indents(TextBlock(s)) == expected
