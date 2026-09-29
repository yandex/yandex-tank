# -*- coding: utf-8 -*-
"""Unit tests for misc module."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from datetime import timedelta

import json
import unittest
import warnings
import requests_mock

from nose.tools import raises
from influxdb.tests import skip_if_pypy, using_pypy

from .client_test import _mocked_session

if not using_pypy:
    import pandas as pd
    from pandas.util.testing import assert_frame_equal
    from influxdb import DataFrameClient
    import numpy as np


@skip_if_pypy
class TestDataFrameClient(unittest.TestCase):
    """Set up a test DataFrameClient object."""

    def setUp(self):
        """Instantiate a TestDataFrameClient object."""
        # By default, raise exceptions on warnings
        warnings.simplefilter('error', FutureWarning)

    def test_write_points_from_dataframe(self):
        """Test write points from df in TestDataFrameClient object."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        dataframe = pd.DataFrame(data=[["1", 1, 1.0], ["2", 2, 2.0]],
                                 index=[now, now + timedelta(hours=1)],
                                 columns=["column_one", "column_two",
                                          "column_three"])
        expected = (
            b"foo column_one=\"1\",column_two=1i,column_three=1.0 0\n"
            b"foo column_one=\"2\",column_two=2i,column_three=2.0 "
            b"3600000000000\n"
        )

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/write",
                           status_code=204)

            cli = DataFrameClient(database='db')

            cli.write_points(dataframe, 'foo')
            self.assertEqual(m.last_request.body, expected)

            cli.write_points(dataframe, 'foo', tags=None)
            self.assertEqual(m.last_request.body, expected)

    def test_dataframe_write_points_with_whitespace_measurement(self):
        """write_points should escape white space in measurements."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        dataframe = pd.DataFrame(data=[["1", 1, 1.0], ["2", 2, 2.0]],
                                 index=[now, now + timedelta(hours=1)],
                                 columns=["column_one", "column_two",
                                          "column_three"])
        expected = (
            b"meas\\ with\\ space "
            b"column_one=\"1\",column_two=1i,column_three=1.0 0\n"
            b"meas\\ with\\ space "
            b"column_one=\"2\",column_two=2i,column_three=2.0 "
            b"3600000000000\n"
        )
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/write",
                           status_code=204)
            cli = DataFrameClient(database='db')
            cli.write_points(dataframe, 'meas with space')
            self.assertEqual(m.last_request.body, expected)

    def test_dataframe_write_points_with_whitespace_in_column_names(self):
        """write_points should escape white space in column names."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        dataframe = pd.DataFrame(data=[["1", 1, 1.0], ["2", 2, 2.0]],
                                 index=[now, now + timedelta(hours=1)],
                                 columns=["column one", "column two",
                                          "column three"])
        expected = (
            b"foo column\\ one=\"1\",column\\ two=1i,column\\ three=1.0 0\n"
            b"foo column\\ one=\"2\",column\\ two=2i,column\\ three=2.0 "
            b"3600000000000\n"
        )
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/write",
                           status_code=204)
            cli = DataFrameClient(database='db')
            cli.write_points(dataframe, 'foo')
            self.assertEqual(m.last_request.body, expected)

    def test_write_points_from_dataframe_with_none(self):
        """Test write points from df in TestDataFrameClient object."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        dataframe = pd.DataFrame(data=[["1", None, 1.0], ["2", 2.0, 2.0]],
                                 index=[now, now + timedelta(hours=1)],
                                 columns=["column_one", "column_two",
                                          "column_three"])
        expected = (
            b"foo column_one=\"1\",column_three=1.0 0\n"
            b"foo column_one=\"2\",column_two=2.0,column_three=2.0 "
            b"3600000000000\n"
        )

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/write",
                           status_code=204)

            cli = DataFrameClient(database='db')

            cli.write_points(dataframe, 'foo')
            self.assertEqual(m.last_request.body, expected)

            cli.write_points(dataframe, 'foo', tags=None)
            self.assertEqual(m.last_request.body, expected)

    def test_write_points_from_dataframe_with_line_of_none(self):
        """Test write points from df in TestDataFrameClient object."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        dataframe = pd.DataFrame(data=[[None, None, None], ["2", 2.0, 2.0]],
                                 index=[now, now + timedelta(hours=1)],
                                 columns=["column_one", "column_two",
                                          "column_three"])
        expected = (
            b"foo column_one=\"2\",column_two=2.0,column_three=2.0 "
            b"3600000000000\n"
        )

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/write",
                           status_code=204)

            cli = DataFrameClient(database='db')

            cli.write_points(dataframe, 'foo')
            self.assertEqual(m.last_request.body, expected)

            cli.write_points(dataframe, 'foo', tags=None)
            self.assertEqual(m.last_request.body, expected)

    def test_write_points_from_dataframe_with_all_none(self):
        """Test write points from df in TestDataFrameClient object."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        dataframe = pd.DataFrame(data=[[None, None, None], [None, None, None]],
                                 index=[now, now + timedelta(hours=1)],
                                 columns=["column_one", "column_two",
                                          "column_three"])
        expected = (
            b"\n"
        )

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/write",
                           status_code=204)

            cli = DataFrameClient(database='db')

            cli.write_points(dataframe, 'foo')
            self.assertEqual(m.last_request.body, expected)

            cli.write_points(dataframe, 'foo', tags=None)
            self.assertEqual(m.last_request.body, expected)

    def test_write_points_from_dataframe_in_batches(self):
        """Test write points in batch from df in TestDataFrameClient object."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        dataframe = pd.DataFrame(data=[["1", 1, 1.0], ["2", 2, 2.0]],
                                 index=[now, now + timedelta(hours=1)],
                                 columns=["column_one", "column_two",
                                          "column_three"])
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/write",
                           status_code=204)

            cli = DataFrameClient(database='db')
            self.assertTrue(cli.write_points(dataframe, "foo", batch_size=1))

    def test_write_points_from_dataframe_with_tag_columns(self):
        """Test write points from df w/tag in TestDataFrameClient object."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        dataframe = pd.DataFrame(data=[['blue', 1, "1", 1, 1.0],
                                       ['red', 0, "2", 2, 2.0]],
                                 index=[now, now + timedelta(hours=1)],
                                 columns=["tag_one", "tag_two", "column_one",
                                          "column_two", "column_three"])
        expected = (
            b"foo,tag_one=blue,tag_two=1 "
            b"column_one=\"1\",column_two=1i,column_three=1.0 "
            b"0\n"
            b"foo,tag_one=red,tag_two=0 "
            b"column_one=\"2\",column_two=2i,column_three=2.0 "
            b"3600000000000\n"
        )

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/write",
                           status_code=204)

            cli = DataFrameClient(database='db')

            cli.write_points(dataframe, 'foo',
                             tag_columns=['tag_one', 'tag_two'])
            self.assertEqual(m.last_request.body, expected)

            cli.write_points(dataframe, 'foo',
                             tag_columns=['tag_one', 'tag_two'], tags=None)
            self.assertEqual(m.last_request.body, expected)

    def test_write_points_from_dataframe_with_tag_cols_and_global_tags(self):
        """Test write points from df w/tag + cols in TestDataFrameClient."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        dataframe = pd.DataFrame(data=[['blue', 1, "1", 1, 1.0],
                                       ['red', 0, "2", 2, 2.0]],
                                 index=[now, now + timedelta(hours=1)],
                                 columns=["tag_one", "tag_two", "column_one",
                                          "column_two", "column_three"])
        expected = (
            b"foo,global_tag=value,tag_one=blue,tag_two=1 "
            b"column_one=\"1\",column_two=1i,column_three=1.0 "
            b"0\n"
            b"foo,global_tag=value,tag_one=red,tag_two=0 "
            b"column_one=\"2\",column_two=2i,column_three=2.0 "
            b"3600000000000\n"
        )

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/write",
                           status_code=204)

            cli = DataFrameClient(database='db')

            cli.write_points(dataframe, 'foo',
                             tag_columns=['tag_one', 'tag_two'],
                             tags={'global_tag': 'value'})
            self.assertEqual(m.last_request.body, expected)

    def test_write_points_from_dataframe_with_tag_cols_and_defaults(self):
        """Test default write points from df w/tag in TestDataFrameClient."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        dataframe = pd.DataFrame(data=[['blue', 1, "1", 1, 1.0, 'hot'],
                                       ['red', 0, "2", 2, 2.0, 'cold']],
                                 index=[now, now + timedelta(hours=1)],
                                 columns=["tag_one", "tag_two", "column_one",
                                          "column_two", "column_three",
                                          "tag_three"])
        expected_tags_and_fields = (
            b"foo,tag_one=blue "
            b"column_one=\"1\",column_two=1i "
            b"0\n"
            b"foo,tag_one=red "
            b"column_one=\"2\",column_two=2i "
            b"3600000000000\n"
        )

        expected_tags_no_fields = (
            b"foo,tag_one=blue,tag_two=1 "
            b"column_one=\"1\",column_two=1i,column_three=1.0,"
            b"tag_three=\"hot\" 0\n"
            b"foo,tag_one=red,tag_two=0 "
            b"column_one=\"2\",column_two=2i,column_three=2.0,"
            b"tag_three=\"cold\" 3600000000000\n"
        )

        expected_fields_no_tags = (
            b"foo,tag_one=blue,tag_three=hot,tag_two=1 "
            b"column_one=\"1\",column_two=1i,column_three=1.0 "
            b"0\n"
            b"foo,tag_one=red,tag_three=cold,tag_two=0 "
            b"column_one=\"2\",column_two=2i,column_three=2.0 "
            b"3600000000000\n"
        )

        expected_no_tags_no_fields = (
            b"foo "
            b"tag_one=\"blue\",tag_two=1i,column_one=\"1\","
            b"column_two=1i,column_three=1.0,tag_three=\"hot\" "
            b"0\n"
            b"foo "
            b"tag_one=\"red\",tag_two=0i,column_one=\"2\","
            b"column_two=2i,column_three=2.0,tag_three=\"cold\" "
            b"3600000000000\n"
        )

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/write",
                           status_code=204)

            cli = DataFrameClient(database='db')

            cli.write_points(dataframe, 'foo',
                             field_columns=['column_one', 'column_two'],
                             tag_columns=['tag_one'])
            self.assertEqual(m.last_request.body, expected_tags_and_fields)

            cli.write_points(dataframe, 'foo',
                             tag_columns=['tag_one', 'tag_two'])
            self.assertEqual(m.last_request.body, expected_tags_no_fields)

            cli.write_points(dataframe, 'foo',
                             field_columns=['column_one', 'column_two',
                                            'column_three'])
            self.assertEqual(m.last_request.body, expected_fields_no_tags)

            cli.write_points(dataframe, 'foo')
            self.assertEqual(m.last_request.body, expected_no_tags_no_fields)

    def test_write_points_from_dataframe_with_tag_escaped(self):
        """Test write points from df w/escaped tag in TestDataFrameClient."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        dataframe = pd.DataFrame(
            data=[
                ['blue orange', "1", 1, 'hot=cold'],  # space, equal
                ['red,green', "2", 2, r'cold\fire'],  # comma, backslash
                ['some', "2", 2, ''],                 # skip empty
                ['some', "2", 2, None],               # skip None
                ['', "2", 2, None],                   # all tags empty
            ],
            index=pd.period_range(now, freq='H', periods=5),
            columns=["tag_one", "column_one", "column_two", "tag_three"]
        )

        expected_escaped_tags = (
            b"foo,tag_one=blue\\ orange,tag_three=hot\\=cold "
            b"column_one=\"1\",column_two=1i "
            b"0\n"
            b"foo,tag_one=red\\,green,tag_three=cold\\\\fire "
            b"column_one=\"2\",column_two=2i "
            b"3600000000000\n"
            b"foo,tag_one=some "
            b"column_one=\"2\",column_two=2i "
            b"7200000000000\n"
            b"foo,tag_one=some "
            b"column_one=\"2\",column_two=2i "
            b"10800000000000\n"
            b"foo "
            b"column_one=\"2\",column_two=2i "
            b"14400000000000\n"
        )

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/write",
                           status_code=204)
            cli = DataFrameClient(database='db')
            cli.write_points(dataframe, 'foo',
                             field_columns=['column_one', 'column_two'],
                             tag_columns=['tag_one', 'tag_three'])
            self.assertEqual(m.last_request.body, expected_escaped_tags)

    def test_write_points_from_dataframe_with_numeric_column_names(self):
        """Test write points from df with numeric cols."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        # df with numeric column names
        dataframe = pd.DataFrame(data=[["1", 1, 1.0], ["2", 2, 2.0]],
                                 index=[now, now + timedelta(hours=1)])

        expected = (
            b'foo,hello=there 0=\"1\",1=1i,2=1.0 0\n'
            b'foo,hello=there 0=\"2\",1=2i,2=2.0 3600000000000\n'
        )

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/write",
                           status_code=204)

            cli = DataFrameClient(database='db')
            cli.write_points(dataframe, "foo", {"hello": "there"})

            self.assertEqual(m.last_request.body, expected)

    def test_write_points_from_dataframe_with_leading_none_column(self):
        """write_points detect erroneous leading comma for null first field."""
        dataframe = pd.DataFrame(
            dict(
                first=[1, None, None, 8, 9],
                second=[2, None, None, None, 10],
                third=[3, 4.1, None, None, 11],
                first_tag=["one", None, None, "eight", None],
                second_tag=["two", None, None, None, None],
                third_tag=["three", "four", None, None, None],
                comment=[
                    "All columns filled",
                    "First two of three empty",
                    "All empty",
                    "Last two of three empty",
                    "Empty tags with values",
                ]
            ),
            index=pd.date_range(
                start=pd.to_datetime('2018-01-01'),
                freq='1D',
                periods=5,
            )
        )
        expected = (
            b'foo,first_tag=one,second_tag=two,third_tag=three'
            b' comment="All columns filled",first=1.0,second=2.0,third=3.0'
            b' 1514764800000000000\n'
            b'foo,third_tag=four'
            b' comment="First two of three empty",third=4.1'
            b' 1514851200000000000\n'
            b'foo comment="All empty" 1514937600000000000\n'
            b'foo,first_tag=eight'
            b' comment="Last two of three empty",first=8.0'
            b' 1515024000000000000\n'
            b'foo'
            b' comment="Empty tags with values",first=9.0,second=10.0'
            b',third=11.0'
            b' 1515110400000000000\n'
        )

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/write",
                           status_code=204)

            cli = DataFrameClient(database='db')

            colnames = [
                "first_tag",
                "second_tag",
                "third_tag",
                "comment",
                "first",
                "second",
                "third"
            ]
            cli.write_points(dataframe.loc[:, colnames], 'foo',
                             tag_columns=[
                                 "first_tag",
                                 "second_tag",
                                 "third_tag"])

            self.assertEqual(m.last_request.body, expected)

    def test_write_points_from_dataframe_with_numeric_precision(self):
        """Test write points from df with numeric precision."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        # df with numeric column names
        dataframe = pd.DataFrame(data=[["1", 1, 1.1111111111111],
                                       ["2", 2, 2.2222222222222]],
                                 index=[now, now + timedelta(hours=1)])

        if np.lib.NumpyVersion(np.__version__) <= '1.13.3':
            expected_default_precision = (
                b'foo,hello=there 0=\"1\",1=1i,2=1.11111111111 0\n'
                b'foo,hello=there 0=\"2\",1=2i,2=2.22222222222 3600000000000\n'
            )
        else:
            expected_default_precision = (
                b'foo,hello=there 0=\"1\",1=1i,2=1.1111111111111 0\n'
                b'foo,hello=there 0=\"2\",1=2i,2=2.2222222222222 3600000000000\n'  # noqa E501 line too long
            )

        expected_specified_precision = (
            b'foo,hello=there 0=\"1\",1=1i,2=1.1111 0\n'
            b'foo,hello=there 0=\"2\",1=2i,2=2.2222 3600000000000\n'
        )

        expected_full_precision = (
            b'foo,hello=there 0=\"1\",1=1i,2=1.1111111111111 0\n'
            b'foo,hello=there 0=\"2\",1=2i,2=2.2222222222222 3600000000000\n'
        )

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/write",
                           status_code=204)

            cli = DataFrameClient(database='db')
            cli.write_points(dataframe, "foo", {"hello": "there"})

            print(expected_default_precision)
            print(m.last_request.body)

            self.assertEqual(m.last_request.body, expected_default_precision)

            cli = DataFrameClient(database='db')
            cli.write_points(dataframe, "foo", {"hello": "there"},
                             numeric_precision=4)

            self.assertEqual(m.last_request.body, expected_specified_precision)

            cli = DataFrameClient(database='db')
            cli.write_points(dataframe, "foo", {"hello": "there"},
                             numeric_precision='full')

            self.assertEqual(m.last_request.body, expected_full_precision)

    def test_write_points_from_dataframe_with_period_index(self):
        """Test write points from df with period index."""
        dataframe = pd.DataFrame(data=[["1", 1, 1.0], ["2", 2, 2.0]],
                                 index=[pd.Period('1970-01-01'),
                                        pd.Period('1970-01-02')],
                                 columns=["column_one", "column_two",
                                          "column_three"])

        expected = (
            b"foo column_one=\"1\",column_two=1i,column_three=1.0 0\n"
            b"foo column_one=\"2\",column_two=2i,column_three=2.0 "
            b"86400000000000\n"
        )

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/write",
                           status_code=204)

            cli = DataFrameClient(database='db')
            cli.write_points(dataframe, "foo")

            self.assertEqual(m.last_request.body, expected)

    def test_write_points_from_dataframe_with_time_precision(self):
        """Test write points from df with time precision."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        dataframe = pd.DataFrame(data=[["1", 1, 1.0], ["2", 2, 2.0]],
                                 index=[now, now + timedelta(hours=1)],
                                 columns=["column_one", "column_two",
                                          "column_three"])

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/write",
                           status_code=204)

            cli = DataFrameClient(database='db')
            measurement = "foo"

            cli.write_points(dataframe, measurement, time_precision='h')
            self.assertEqual(m.last_request.qs['precision'], ['h'])
            self.assertEqual(
                b'foo column_one="1",column_two=1i,column_three=1.0 0\nfoo '
                b'column_one="2",column_two=2i,column_three=2.0 1\n',
                m.last_request.body,
            )

            cli.write_points(dataframe, measurement, time_precision='m')
            self.assertEqual(m.last_request.qs['precision'], ['m'])
            self.assertEqual(
                b'foo column_one="1",column_two=1i,column_three=1.0 0\nfoo '
                b'column_one="2",column_two=2i,column_three=2.0 60\n',
                m.last_request.body,
            )

            cli.write_points(dataframe, measurement, time_precision='s')
            self.assertEqual(m.last_request.qs['precision'], ['s'])
            self.assertEqual(
                b'foo column_one="1",column_two=1i,column_three=1.0 0\nfoo '
                b'column_one="2",column_two=2i,column_three=2.0 3600\n',
                m.last_request.body,
            )

            cli.write_points(dataframe, measurement, time_precision='ms')
            self.assertEqual(m.last_request.qs['precision'], ['ms'])
            self.assertEqual(
                b'foo column_one="1",column_two=1i,column_three=1.0 0\nfoo '
                b'column_one="2",column_two=2i,column_three=2.0 3600000\n',
                m.last_request.body,
            )

            cli.write_points(dataframe, measurement, time_precision='u')
            self.assertEqual(m.last_request.qs['precision'], ['u'])
            self.assertEqual(
                b'foo column_one="1",column_two=1i,column_three=1.0 0\nfoo '
                b'column_one="2",column_two=2i,column_three=2.0 3600000000\n',
                m.last_request.body,
            )

            cli.write_points(dataframe, measurement, time_precision='n')
            self.assertEqual(m.last_request.qs['precision'], ['n'])
            self.assertEqual(
                b'foo column_one="1",column_two=1i,column_three=1.0 0\n'
                b'foo column_one="2",column_two=2i,column_three=2.0 '
                b'3600000000000\n',
                m.last_request.body,
            )

    @raises(TypeError)
    def test_write_points_from_dataframe_fails_without_time_index(self):
        """Test failed write points from df without time index."""
        dataframe = pd.DataFrame(data=[["1", 1, 1.0], ["2", 2, 2.0]],
                                 columns=["column_one", "column_two",
                                          "column_three"])

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/db/db/series",
                           status_code=204)

            cli = DataFrameClient(database='db')
            cli.write_points(dataframe, "foo")

    @raises(TypeError)
    def test_write_points_from_dataframe_fails_with_series(self):
        """Test failed write points from df with series."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        dataframe = pd.Series(data=[1.0, 2.0],
                              index=[now, now + timedelta(hours=1)])

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/db/db/series",
                           status_code=204)

            cli = DataFrameClient(database='db')
            cli.write_points(dataframe, "foo")

    def test_create_database(self):
        """Test create database for TestInfluxDBClient object."""
        cli = DataFrameClient(database='db')
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/query",
                text='{"results":[{}]}'
            )
            cli.create_database('new_db')
            self.assertEqual(
                m.last_request.qs['q'][0],
                'create database "new_db"'
            )

    def test_create_numeric_named_database(self):
        """Test create db w/numeric name for TestInfluxDBClient object."""
        cli = DataFrameClient(database='db')
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/query",
                text='{"results":[{}]}'
            )
            cli.create_database('123')
            self.assertEqual(
                m.last_request.qs['q'][0],
                'create database "123"'
            )

    @raises(Exception)
    def test_create_database_fails(self):
        """Test create database fail for TestInfluxDBClient object."""
        cli = DataFrameClient(database='db')
        with _mocked_session(cli, 'post', 401):
            cli.create_database('new_db')

    def test_drop_database(self):
        """Test drop database for TestInfluxDBClient object."""
        cli = DataFrameClient(database='db')
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/query",
                text='{"results":[{}]}'
            )
            cli.drop_database('new_db')
            self.assertEqual(
                m.last_request.qs['q'][0],
                'drop database "new_db"'
            )

    def test_drop_measurement(self):
        """Test drop measurement for TestInfluxDBClient object."""
        cli = DataFrameClient(database='db')
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/query",
                text='{"results":[{}]}'
            )
            cli.drop_measurement('new_measurement')
            self.assertEqual(
                m.last_request.qs['q'][0],
                'drop measurement "new_measurement"'
            )

    def test_drop_numeric_named_database(self):
        """Test drop numeric db for TestInfluxDBClient object."""
        cli = DataFrameClient(database='db')
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/query",
                text='{"results":[{}]}'
            )
            cli.drop_database('123')
            self.assertEqual(
                m.last_request.qs['q'][0],
                'drop database "123"'
            )

    @raises(Exception)
    def test_get_list_database_fails(self):
        """Test get list of dbs fail for TestInfluxDBClient object."""
        cli = DataFrameClient('host', 8086, 'username', 'password')
        with _mocked_session(cli, 'get', 401):
            cli.get_list_database()

    def test_get_list_measurements(self):
        """Test get list of measurements for TestInfluxDBClient object."""
        cli = DataFrameClient(database='db')
        data = {
            "results": [{
                "series": [
                    {"name": "measurements",
                     "columns": ["name"],
                     "values": [["cpu"], ["disk"]
                                ]}]}
            ]
        }

        with _mocked_session(cli, 'get', 200, json.dumps(data)):
            self.assertListEqual(
                cli.get_list_measurements(),
                [{'name': 'cpu'}, {'name': 'disk'}]
            )

    def test_create_retention_policy_default(self):
        """Test create default ret policy for TestInfluxDBClient object."""
        cli = DataFrameClient(database='db')
        example_response = '{"results":[{}]}'

        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/query",
                text=example_response
            )
            cli.create_retention_policy(
                'somename', '1d', 4, default=True, database='db'
            )

            self.assertEqual(
                m.last_request.qs['q'][0],
                'create retention policy "somename" on '
                '"db" duration 1d replication 4 shard duration 0s default'
            )

    def test_create_retention_policy(self):
        """Test create retention policy for TestInfluxDBClient object."""
        cli = DataFrameClient(database='db')
        example_response = '{"results":[{}]}'

        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/query",
                text=example_response
            )
            cli.create_retention_policy(
                'somename', '1d', 4, database='db'
            )

            self.assertEqual(
                m.last_request.qs['q'][0],
                'create retention policy "somename" on '
                '"db" duration 1d replication 4 shard duration 0s'
            )

    def test_alter_retention_policy(self):
        """Test alter retention policy for TestInfluxDBClient object."""
        cli = DataFrameClient(database='db')
        example_response = '{"results":[{}]}'

        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/query",
                text=example_response
            )
            # Test alter duration
            cli.alter_retention_policy('somename', 'db',
                                       duration='4d')
            self.assertEqual(
                m.last_request.qs['q'][0],
                'alter retention policy "somename" on "db" duration 4d'
            )
            # Test alter replication
            cli.alter_retention_policy('somename', 'db',
                                       replication=4)
            self.assertEqual(
                m.last_request.qs['q'][0],
                'alter retention policy "somename" on "db" replication 4'
            )

            # Test alter shard duration
            cli.alter_retention_policy('somename', 'db',
                                       shard_duration='1h')
            self.assertEqual(
                m.last_request.qs['q'][0],
                'alter retention policy "somename" on "db" shard duration 1h'
            )

            # Test alter default
            cli.alter_retention_policy('somename', 'db',
                                       default=True)
            self.assertEqual(
                m.last_request.qs['q'][0],
                'alter retention policy "somename" on "db" default'
            )

    @raises(Exception)
    def test_alter_retention_policy_invalid(self):
        """Test invalid alter ret policy for TestInfluxDBClient object."""
        cli = DataFrameClient('host', 8086, 'username', 'password')
        with _mocked_session(cli, 'get', 400):
            cli.alter_retention_policy('somename', 'db')

    def test_drop_retention_policy(self):
        """Test drop retention policy for TestInfluxDBClient object."""
        cli = DataFrameClient(database='db')
        example_response = '{"results":[{}]}'

        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/query",
                text=example_response
            )
            cli.drop_retention_policy('somename', 'db')
            self.assertEqual(
                m.last_request.qs['q'][0],
                'drop retention policy "somename" on "db"'
            )

    @raises(Exception)
    def test_drop_retention_policy_fails(self):
        """Test failed drop ret policy for TestInfluxDBClient object."""
        cli = DataFrameClient('host', 8086, 'username', 'password')
        with _mocked_session(cli, 'delete', 401):
            cli.drop_retention_policy('default', 'db')

    def test_get_list_retention_policies(self):
        """Test get retention policies for TestInfluxDBClient object."""
        cli = DataFrameClient(database='db')
        example_response = \
            '{"results": [{"series": [{"values": [["fsfdsdf", "24h0m0s", 2]],'\
            ' "columns": ["name", "duration", "replicaN"]}]}]}'

        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.GET,
                "http://localhost:8086/query",
                text=example_response
            )
            self.assertListEqual(
                cli.get_list_retention_policies("db"),
                [{'duration': '24h0m0s',
                  'name': 'fsfdsdf', 'replicaN': 2}]
            )

    def test_query_into_dataframe(self):
        """Test query into df for TestDataFrameClient object."""
        data = {
            "results": [{
                "series": [
                    {"measurement": "network",
                     "tags": {"direction": ""},
                     "columns": ["time", "value"],
                     "values": [["2009-11-10T23:00:00Z", 23422]]
                     },
                    {"measurement": "network",
                     "tags": {"direction": "in"},
                     "columns": ["time", "value"],
                     "values": [["2009-11-10T23:00:00Z", 23422],
                                ["2009-11-10T23:00:00Z", 23422],
                                ["2009-11-10T23:00:00Z", 23422]]
                     }
                ]
            }]
        }

        pd1 = pd.DataFrame(
            [[23422]], columns=['value'],
            index=pd.to_datetime(["2009-11-10T23:00:00Z"]))
        if pd1.index.tzinfo is None:
            pd1.index = pd1.index.tz_localize('UTC')
        pd2 = pd.DataFrame(
            [[23422], [23422], [23422]], columns=['value'],
            index=pd.to_datetime(["2009-11-10T23:00:00Z",
                                  "2009-11-10T23:00:00Z",
                                  "2009-11-10T23:00:00Z"]))
        if pd2.index.tzinfo is None:
            pd2.index = pd2.index.tz_localize('UTC')
        expected = {
            ('network', (('direction', ''),)): pd1,
            ('network', (('direction', 'in'),)): pd2
        }

        cli = DataFrameClient('host', 8086, 'username', 'password', 'db')
        with _mocked_session(cli, 'GET', 200, data):
            result = cli.query('select value from network group by direction;')
            for k in expected:
                assert_frame_equal(expected[k], result[k])

    def test_multiquery_into_dataframe(self):
        """Test multiquery into df for TestDataFrameClient object."""
        data = {
            "results": [
                {
                    "series": [
                        {
                            "name": "cpu_load_short",
                            "columns": ["time", "value"],
                            "values": [
                                ["2015-01-29T21:55:43.702900257Z", 0.55],
                                ["2015-01-29T21:55:43.702900257Z", 23422],
                                ["2015-06-11T20:46:02Z", 0.64]
                            ]
                        }
                    ]
                }, {
                    "series": [
                        {
                            "name": "cpu_load_short",
                            "columns": ["time", "count"],
                            "values": [
                                ["1970-01-01T00:00:00Z", 3]
                            ]
                        }
                    ]
                }
            ]
        }

        pd1 = pd.DataFrame(
            [[0.55], [23422.0], [0.64]], columns=['value'],
            index=pd.to_datetime([
                "2015-01-29 21:55:43.702900257+0000",
                "2015-01-29 21:55:43.702900257+0000",
                "2015-06-11 20:46:02+0000"]))
        if pd1.index.tzinfo is None:
            pd1.index = pd1.index.tz_localize('UTC')
        pd2 = pd.DataFrame(
            [[3]], columns=['count'],
            index=pd.to_datetime(["1970-01-01 00:00:00+00:00"]))
        if pd2.index.tzinfo is None:
            pd2.index = pd2.index.tz_localize('UTC')
        expected = [{'cpu_load_short': pd1}, {'cpu_load_short': pd2}]

        cli = DataFrameClient('host', 8086, 'username', 'password', 'db')
        iql = "SELECT value FROM cpu_load_short WHERE region=$region;"\
            "SELECT count(value) FROM cpu_load_short WHERE region=$region"
        bind_params = {'region': 'us-west'}
        with _mocked_session(cli, 'GET', 200, data):
            result = cli.query(iql, bind_params=bind_params)
            for r, e in zip(result, expected):
                for k in e:
                    assert_frame_equal(e[k], r[k])

    def test_multiquery_into_dataframe_dropna(self):
        """Test multiquery into df for TestDataFrameClient object."""
        data = {
            "results": [
                {
                    "series": [
                        {
                            "name": "cpu_load_short",
                            "columns": ["time", "value", "value2", "value3"],
                            "values": [
                                ["2015-01-29T21:55:43.702900257Z",
                                 0.55, 0.254, np.NaN],
                                ["2015-01-29T21:55:43.702900257Z",
                                 23422, 122878, np.NaN],
                                ["2015-06-11T20:46:02Z",
                                 0.64, 0.5434, np.NaN]
                            ]
                        }
                    ]
                }, {
                    "series": [
                        {
                            "name": "cpu_load_short",
                            "columns": ["time", "count"],
                            "values": [
                                ["1970-01-01T00:00:00Z", 3]
                            ]
                        }
                    ]
                }
            ]
        }

        pd1 = pd.DataFrame(
            [[0.55, 0.254, np.NaN],
             [23422.0, 122878, np.NaN],
             [0.64, 0.5434, np.NaN]],
            columns=['value', 'value2', 'value3'],
            index=pd.to_datetime([
                "2015-01-29 21:55:43.702900257+0000",
                "2015-01-29 21:55:43.702900257+0000",
                "2015-06-11 20:46:02+0000"]))

        if pd1.index.tzinfo is None:
            pd1.index = pd1.index.tz_localize('UTC')

        pd1_dropna = pd.DataFrame(
            [[0.55, 0.254], [23422.0, 122878], [0.64, 0.5434]],
            columns=['value', 'value2'],
            index=pd.to_datetime([
                "2015-01-29 21:55:43.702900257+0000",
                "2015-01-29 21:55:43.702900257+0000",
                "2015-06-11 20:46:02+0000"]))

        if pd1_dropna.index.tzinfo is None:
            pd1_dropna.index = pd1_dropna.index.tz_localize('UTC')

        pd2 = pd.DataFrame(
            [[3]], columns=['count'],
            index=pd.to_datetime(["1970-01-01 00:00:00+00:00"]))

        if pd2.index.tzinfo is None:
            pd2.index = pd2.index.tz_localize('UTC')

        expected_dropna_true = [
            {'cpu_load_short': pd1_dropna},
            {'cpu_load_short': pd2}]
        expected_dropna_false = [
            {'cpu_load_short': pd1},
            {'cpu_load_short': pd2}]

        cli = DataFrameClient('host', 8086, 'username', 'password', 'db')
        iql = "SELECT value FROM cpu_load_short WHERE region=$region;" \
              "SELECT count(value) FROM cpu_load_short WHERE region=$region"
        bind_params = {'region': 'us-west'}

        for dropna in [True, False]:
            with _mocked_session(cli, 'GET', 200, data):
                result = cli.query(iql, bind_params=bind_params, dropna=dropna)
                expected = \
                    expected_dropna_true if dropna else expected_dropna_false
                for r, e in zip(result, expected):
                    for k in e:
                        assert_frame_equal(e[k], r[k])

        # test default value (dropna = True)
        with _mocked_session(cli, 'GET', 200, data):
            result = cli.query(iql, bind_params=bind_params)
            for r, e in zip(result, expected_dropna_true):
                for k in e:
                    assert_frame_equal(e[k], r[k])

    def test_query_with_empty_result(self):
        """Test query with empty results in TestDataFrameClient object."""
        cli = DataFrameClient('host', 8086, 'username', 'password', 'db')
        with _mocked_session(cli, 'GET', 200, {"results": [{}]}):
            result = cli.query('select column_one from foo;')
            self.assertEqual(result, {})

    def test_get_list_database(self):
        """Test get list of databases in TestDataFrameClient object."""
        data = {'results': [
            {'series': [
                {'measurement': 'databases',
                 'values': [
                     ['new_db_1'],
                     ['new_db_2']],
                 'columns': ['name']}]}
        ]}

        cli = DataFrameClient('host', 8086, 'username', 'password', 'db')
        with _mocked_session(cli, 'get', 200, json.dumps(data)):
            self.assertListEqual(
                cli.get_list_database(),
                [{'name': 'new_db_1'}, {'name': 'new_db_2'}]
            )

    def test_datetime_to_epoch(self):
        """Test convert datetime to epoch in TestDataFrameClient object."""
        timestamp = pd.Timestamp('2013-01-01 00:00:00.000+00:00')
        cli = DataFrameClient('host', 8086, 'username', 'password', 'db')

        self.assertEqual(
            cli._datetime_to_epoch(timestamp),
            1356998400.0
        )
        self.assertEqual(
            cli._datetime_to_epoch(timestamp, time_precision='h'),
            1356998400.0 / 3600
        )
        self.assertEqual(
            cli._datetime_to_epoch(timestamp, time_precision='m'),
            1356998400.0 / 60
        )
        self.assertEqual(
            cli._datetime_to_epoch(timestamp, time_precision='s'),
            1356998400.0
        )
        self.assertEqual(
            cli._datetime_to_epoch(timestamp, time_precision='ms'),
            1356998400000.0
        )
        self.assertEqual(
            cli._datetime_to_epoch(timestamp, time_precision='u'),
            1356998400000000.0
        )
        self.assertEqual(
            cli._datetime_to_epoch(timestamp, time_precision='n'),
            1356998400000000000.0
        )

    def test_dsn_constructor(self):
        """Test data source name deconstructor in TestDataFrameClient."""
        client = DataFrameClient.from_dsn('influxdb://localhost:8086')
        self.assertIsInstance(client, DataFrameClient)
        self.assertEqual('http://localhost:8086', client._baseurl)

    def test_write_points_from_dataframe_with_nan_line(self):
        """Test write points from dataframe with Nan lines."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        dataframe = pd.DataFrame(data=[["1", 1, np.inf], ["2", 2, np.nan]],
                                 index=[now, now + timedelta(hours=1)],
                                 columns=["column_one", "column_two",
                                          "column_three"])
        expected = (
            b"foo column_one=\"1\",column_two=1i 0\n"
            b"foo column_one=\"2\",column_two=2i "
            b"3600000000000\n"
        )

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/write",
                           status_code=204)

            cli = DataFrameClient(database='db')

            cli.write_points(dataframe, 'foo', protocol='line')
            self.assertEqual(m.last_request.body, expected)

            cli.write_points(dataframe, 'foo', tags=None, protocol='line')
            self.assertEqual(m.last_request.body, expected)

    def test_write_points_from_dataframe_with_nan_json(self):
        """Test write points from json with NaN lines."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        dataframe = pd.DataFrame(data=[["1", 1, np.inf], ["2", 2, np.nan]],
                                 index=[now, now + timedelta(hours=1)],
                                 columns=["column_one", "column_two",
                                          "column_three"])
        expected = (
            b"foo column_one=\"1\",column_two=1i 0\n"
            b"foo column_one=\"2\",column_two=2i "
            b"3600000000000\n"
        )

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/write",
                           status_code=204)

            cli = DataFrameClient(database='db')

            cli.write_points(dataframe, 'foo', protocol='json')
            self.assertEqual(m.last_request.body, expected)

            cli.write_points(dataframe, 'foo', tags=None, protocol='json')
            self.assertEqual(m.last_request.body, expected)

    def test_write_points_from_dataframe_with_tags_and_nan_line(self):
        """Test write points from dataframe with NaN lines and tags."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        dataframe = pd.DataFrame(data=[['blue', 1, "1", 1, np.inf],
                                       ['red', 0, "2", 2, np.nan]],
                                 index=[now, now + timedelta(hours=1)],
                                 columns=["tag_one", "tag_two", "column_one",
                                          "column_two", "column_three"])
        expected = (
            b"foo,tag_one=blue,tag_two=1 "
            b"column_one=\"1\",column_two=1i "
            b"0\n"
            b"foo,tag_one=red,tag_two=0 "
            b"column_one=\"2\",column_two=2i "
            b"3600000000000\n"
        )

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/write",
                           status_code=204)

            cli = DataFrameClient(database='db')

            cli.write_points(dataframe, 'foo', protocol='line',
                             tag_columns=['tag_one', 'tag_two'])
            self.assertEqual(m.last_request.body, expected)

            cli.write_points(dataframe, 'foo', tags=None, protocol='line',
                             tag_columns=['tag_one', 'tag_two'])
            self.assertEqual(m.last_request.body, expected)

    def test_write_points_from_dataframe_with_tags_and_nan_json(self):
        """Test write points from json with NaN lines and tags."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        dataframe = pd.DataFrame(data=[['blue', 1, "1", 1, np.inf],
                                       ['red', 0, "2", 2, np.nan]],
                                 index=[now, now + timedelta(hours=1)],
                                 columns=["tag_one", "tag_two", "column_one",
                                          "column_two", "column_three"])
        expected = (
            b"foo,tag_one=blue,tag_two=1 "
            b"column_one=\"1\",column_two=1i "
            b"0\n"
            b"foo,tag_one=red,tag_two=0 "
            b"column_one=\"2\",column_two=2i "
            b"3600000000000\n"
        )

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/write",
                           status_code=204)

            cli = DataFrameClient(database='db')

            cli.write_points(dataframe, 'foo', protocol='json',
                             tag_columns=['tag_one', 'tag_two'])
            self.assertEqual(m.last_request.body, expected)

            cli.write_points(dataframe, 'foo', tags=None, protocol='json',
                             tag_columns=['tag_one', 'tag_two'])
            self.assertEqual(m.last_request.body, expected)

    def test_query_custom_index(self):
        """Test query with custom indexes."""
        data = {
            "results": [
                {
                    "series": [
                        {
                            "name": "cpu_load_short",
                            "columns": ["time", "value", "host"],
                            "values": [
                                [1, 0.55, "local"],
                                [2, 23422, "local"],
                                [3, 0.64, "local"]
                            ]
                        }
                    ]
                }
            ]
        }

        cli = DataFrameClient('host', 8086, 'username', 'password', 'db')
        iql = "SELECT value FROM cpu_load_short WHERE region=$region;" \
              "SELECT count(value) FROM cpu_load_short WHERE region=$region"
        bind_params = {'region': 'us-west'}
        with _mocked_session(cli, 'GET', 200, data):
            result = cli.query(iql, bind_params=bind_params,
                               data_frame_index=["time", "host"])

            _data_frame = result['cpu_load_short']
            print(_data_frame)

            self.assertListEqual(["time", "host"],
                                 list(_data_frame.index.names))

    def test_dataframe_nanosecond_precision(self):
        """Test nanosecond precision."""
        for_df_dict = {
            "nanFloats": [1.1, float('nan'), 3.3, 4.4],
            "onlyFloats": [1.1, 2.2, 3.3, 4.4],
            "strings": ['one_one', 'two_two', 'three_three', 'four_four']
        }
        df = pd.DataFrame.from_dict(for_df_dict)
        df['time'] = ['2019-10-04 06:27:19.850557111+00:00',
                      '2019-10-04 06:27:19.850557184+00:00',
                      '2019-10-04 06:27:42.251396864+00:00',
                      '2019-10-04 06:27:42.251396974+00:00']
        df['time'] = pd.to_datetime(df['time'], unit='ns')
        df = df.set_index('time')

        expected = (
            b'foo nanFloats=1.1,onlyFloats=1.1,strings="one_one" 1570170439850557111\n'  # noqa E501 line too long
            b'foo onlyFloats=2.2,strings="two_two" 1570170439850557184\n'  # noqa E501 line too long
            b'foo nanFloats=3.3,onlyFloats=3.3,strings="three_three" 1570170462251396864\n'  # noqa E501 line too long
            b'foo nanFloats=4.4,onlyFloats=4.4,strings="four_four" 1570170462251396974\n'  # noqa E501 line too long
        )

        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/write",
                status_code=204
            )

            cli = DataFrameClient(database='db')
            cli.write_points(df, 'foo', time_precision='n')

            self.assertEqual(m.last_request.body, expected)

    def test_dataframe_nanosecond_precision_one_microsecond(self):
        """Test nanosecond precision within one microsecond."""
        # 1 microsecond = 1000 nanoseconds
        start = np.datetime64('2019-10-04T06:27:19.850557000')
        end = np.datetime64('2019-10-04T06:27:19.850558000')

        # generate timestamps with nanosecond precision
        timestamps = np.arange(
            start,
            end + np.timedelta64(1, 'ns'),
            np.timedelta64(1, 'ns')
        )
        # generate values
        values = np.arange(0.0, len(timestamps))

        df = pd.DataFrame({'value': values}, index=timestamps)
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/write",
                status_code=204
            )

            cli = DataFrameClient(database='db')
            cli.write_points(df, 'foo', time_precision='n')

            lines = m.last_request.body.decode('utf-8').split('\n')
            self.assertEqual(len(lines), 1002)

            for index, line in enumerate(lines):
                if index == 1001:
                    self.assertEqual(line, '')
                    continue
                self.assertEqual(
                    line,
                    f"foo value={index}.0 157017043985055{7000 + index:04}"
                )
