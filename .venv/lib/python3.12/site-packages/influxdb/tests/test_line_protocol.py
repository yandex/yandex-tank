# -*- coding: utf-8 -*-
"""Define the line protocol test module."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from datetime import datetime
from decimal import Decimal

from pytz import UTC, timezone
from influxdb import line_protocol


class TestLineProtocol(unittest.TestCase):
    """Define the LineProtocol test object."""

    def test_make_lines(self):
        """Test make new lines in TestLineProtocol object."""
        data = {
            "tags": {
                "empty_tag": "",
                "none_tag": None,
                "backslash_tag": "C:\\",
                "integer_tag": 2,
                "string_tag": "hello"
            },
            "points": [
                {
                    "measurement": "test",
                    "fields": {
                        "string_val": "hello!",
                        "int_val": 1,
                        "float_val": 1.1,
                        "none_field": None,
                        "bool_val": True,
                    }
                }
            ]
        }

        self.assertEqual(
            line_protocol.make_lines(data),
            'test,backslash_tag=C:\\\\,integer_tag=2,string_tag=hello '
            'bool_val=True,float_val=1.1,int_val=1i,string_val="hello!"\n'
        )

    def test_timezone(self):
        """Test timezone in TestLineProtocol object."""
        dt = datetime(2009, 11, 10, 23, 0, 0, 123456)
        utc = UTC.localize(dt)
        berlin = timezone('Europe/Berlin').localize(dt)
        eastern = berlin.astimezone(timezone('US/Eastern'))
        data = {
            "points": [
                {"measurement": "A", "fields": {"val": 1},
                 "time": 0},
                {"measurement": "A", "fields": {"val": 1},
                 "time": "2009-11-10T23:00:00.123456Z"},
                {"measurement": "A", "fields": {"val": 1}, "time": dt},
                {"measurement": "A", "fields": {"val": 1}, "time": utc},
                {"measurement": "A", "fields": {"val": 1}, "time": berlin},
                {"measurement": "A", "fields": {"val": 1}, "time": eastern},
            ]
        }
        self.assertEqual(
            line_protocol.make_lines(data),
            '\n'.join([
                'A val=1i 0',
                'A val=1i 1257894000123456000',
                'A val=1i 1257894000123456000',
                'A val=1i 1257894000123456000',
                'A val=1i 1257890400123456000',
                'A val=1i 1257890400123456000',
            ]) + '\n'
        )

    def test_string_val_newline(self):
        """Test string value with newline in TestLineProtocol object."""
        data = {
            "points": [
                {
                    "measurement": "m1",
                    "fields": {
                        "multi_line": "line1\nline1\nline3"
                    }
                }
            ]
        }

        self.assertEqual(
            line_protocol.make_lines(data),
            'm1 multi_line="line1\\nline1\\nline3"\n'
        )

    def test_make_lines_unicode(self):
        """Test make unicode lines in TestLineProtocol object."""
        data = {
            "tags": {
                "unicode_tag": "\'Привет!\'"  # Hello! in Russian
            },
            "points": [
                {
                    "measurement": "test",
                    "fields": {
                        "unicode_val": "Привет!",  # Hello! in Russian
                    }
                }
            ]
        }

        self.assertEqual(
            line_protocol.make_lines(data),
            'test,unicode_tag=\'Привет!\' unicode_val="Привет!"\n'
        )

    def test_make_lines_empty_field_string(self):
        """Test make lines with an empty string field."""
        data = {
            "points": [
                {
                    "measurement": "test",
                    "fields": {
                        "string": "",
                    }
                }
            ]
        }

        self.assertEqual(
            line_protocol.make_lines(data),
            'test string=""\n'
        )

    def test_tag_value_newline(self):
        """Test make lines with tag value contains newline."""
        data = {
            "tags": {
                "t1": "line1\nline2"
            },
            "points": [
                {
                    "measurement": "test",
                    "fields": {
                        "val": "hello"
                    }
                }
            ]
        }

        self.assertEqual(
            line_protocol.make_lines(data),
            'test,t1=line1\\nline2 val="hello"\n'
        )

    def test_quote_ident(self):
        """Test quote indentation in TestLineProtocol object."""
        self.assertEqual(
            line_protocol.quote_ident(r"""\foo ' bar " Örf"""),
            r'''"\\foo ' bar \" Örf"'''
        )

    def test_quote_literal(self):
        """Test quote literal in TestLineProtocol object."""
        self.assertEqual(
            line_protocol.quote_literal(r"""\foo ' bar " Örf"""),
            r"""'\\foo \' bar " Örf'"""
        )

    def test_float_with_long_decimal_fraction(self):
        """Ensure precision is preserved when casting floats into strings."""
        data = {
            "points": [
                {
                    "measurement": "test",
                    "fields": {
                        "float_val": 1.0000000000000009,
                    }
                }
            ]
        }
        self.assertEqual(
            line_protocol.make_lines(data),
            'test float_val=1.0000000000000009\n'
        )

    def test_float_with_long_decimal_fraction_as_type_decimal(self):
        """Ensure precision is preserved when casting Decimal into strings."""
        data = {
            "points": [
                {
                    "measurement": "test",
                    "fields": {
                        "float_val": Decimal(0.8289445733333332),
                    }
                }
            ]
        }
        self.assertEqual(
            line_protocol.make_lines(data),
            'test float_val=0.8289445733333332\n'
        )
