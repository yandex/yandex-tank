# coding=utf-8
import pytest

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
    def test_any_of_list(self, texts, expected):
        assert RSTFormatter.bullet_list([TextBlock(text) for text in texts]) == expected


@pytest.mark.skip
@pytest.mark.parametrize('schema_filename, expected', [
    ('yandextank/plugins/Telegraf/config/schema.yaml',
     """kill_old
========
:default: True
:type: list
:elements:
 :type: string
 :allowed: foo

default_target
==============
:default: localhost
:any of:
 - :type: list
   :elements:
    :type: string
 - :type: string  
   :allowed: auto  """)
])
def test_format_schema(schema_filename, expected):
    raise NotImplemented