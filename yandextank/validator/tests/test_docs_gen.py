# coding=utf-8
import pytest
import yaml

from yandextank.validator.docs_gen import RSTFormatter, TextBlock, format_schema


class TestRSTFormatter(object):

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
    def test_any_of_table(self, s1, s2, expected):
        assert RSTFormatter.any_of_table([TextBlock(s1), TextBlock(s2)]) == expected

    @pytest.mark.parametrize('s, expected',[
        ('type: list\nelements:\n\ttype: string', '| type: list\n| elements:\n|   type: string'),
        ('type: string\nallowed: auto\ndescription:', '| type: string\n| allowed: auto\n| description:')
    ])
    def test_preserve_indents(self, s, expected):
        assert RSTFormatter.preserve_indents(TextBlock(s)) == expected

    @pytest.mark.parametrize('s, expected',[
        ('A nice title',
         'A nice title\n============'),
        ('A nice\ntitle',
         'A nice title\n============'),
        (u'Широкая электрификация южных губерний',
         u'Широкая электрификация южных губерний\n====================================='),
        (u'Широкая электрификация\nюжных губерний',
         u'Широкая электрификация южных губерний\n====================================='),
        (u'Широкая электрификация\n\tюжных губерний',
         u'Широкая электрификация   южных губерний\n======================================='),
    ])
    def test_title(self, s, expected):
        assert RSTFormatter.title(s) == expected

    @pytest.mark.parametrize('block, expected', [
        (':type: list\n:elements:\n\t:type: string',
         """- :type: list
  :elements:
    :type: string"""
         )
    ])
    def test__list_item(self, block, expected):
        assert RSTFormatter._list_item(TextBlock(block)) == expected

    @pytest.mark.parametrize('texts, expected', [
        ([
            ':type: list\n:elements:\n\t:type: string',
            ':type: string\n:allowed: auto'
        ],
        """- :type: list
  :elements:
    :type: string
- :type: string
  :allowed: auto"""),
        ([
             ':type: list\n:elements:\n :type: string',
             ':type: string\n:allowed: auto'
         ],
         """- :type: list
  :elements:
   :type: string
- :type: string
  :allowed: auto""")
    ])
    def test_bullet_list(self, texts, expected):
        assert str(RSTFormatter.bullet_list([TextBlock(text) for text in texts])) == expected

    @pytest.mark.parametrize('items, expected', [
        ({'default': 'True', 'type': 'list'},
         """:default:\n True\n:type:\n list\n"""),
        ({'defa\nult': 'True', 'type': 'list'},
         """:defa ult:\n True\n:type:\n list\n"""),
        ({'type': 'list', 'elements': ':type: string\n:allowed: foo'},
         """:elements:
 :type: string
 :allowed: foo
:type:
 list\n"""),
        ({'type': 'list', 'elements': {'type': 'string', 'allowed': 'foo'}},
         """:elements:
 :allowed:
  foo
 :type:
  string
:type:
 list\n""")
    ])
    def test_field_list(self, items, expected):
        assert str(RSTFormatter.field_list(items, sort=True)) == expected

    @pytest.mark.parametrize('structure, expected', [
        ('simple\nstring', 'simple\nstring'),
        (['simple', 'list'], '- simple\n- list'),
        (['nested', ['list', 'here'], 'yes'], '- nested\n- - list\n  - here\n- yes'),
        ({'simple': 'dict', 'single': 'level'}, ':simple:\n dict\n:single:\n level\n'),
        ({'nested': {'dict': 'nested'}, 'other': 'staff'}, ':nested:\n :dict:\n  nested\n:other:\n staff\n'),
        ({'nested': ['list', 0, 1], 'other': 'staff'}, ':nested:\n - list\n - 0\n - 1\n:other:\n staff\n'),
        ({'default': 'localhost', 'any of': [{'type': 'list', 'elements': {'type': 'string'}},
                                             {'type': 'string', 'allowed': 'auto'}]},
         """:any of:
 - :elements:
    :type:
     string
   :type:
    list
 - :allowed:
    auto
   :type:
    string
:default:
 localhost
""")
    ])
    def test_dict_list_structure(self, structure, expected):
        assert str(RSTFormatter.dict_list_structure(structure)) == expected


@pytest.mark.parametrize('schema_filename, expected', [
    ('yandextank/validator/tests/test_schema.yaml',
     """kill_old
========
:default:
 - foo
 - bar

:elements:
 :allowed:
  - foo
  - bar
 :type:
  string
:type:
 list

default_target
==============
:default:
 localhost

:any of:
 - :elements:
    :type:
     string
   :type:
    list
 - :allowed:
    auto
   :type:
    string
""")
])
def test_format_schema(schema_filename, expected):
    with open(schema_filename) as f:
        schema = yaml.load(f)
    assert format_schema(schema, RSTFormatter()) == expected