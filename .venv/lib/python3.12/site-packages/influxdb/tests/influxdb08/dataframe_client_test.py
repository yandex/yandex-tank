# -*- coding: utf-8 -*-
"""Unit tests for misc module."""

from datetime import timedelta

import copy
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
    from influxdb.influxdb08 import DataFrameClient


@skip_if_pypy
class TestDataFrameClient(unittest.TestCase):
    """Define the DataFramClient test object."""

    def setUp(self):
        """Set up an instance of TestDataFrameClient object."""
        # By default, raise exceptions on warnings
        warnings.simplefilter('error', FutureWarning)

    def test_write_points_from_dataframe(self):
        """Test write points from dataframe."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        dataframe = pd.DataFrame(data=[["1", 1, 1.0], ["2", 2, 2.0]],
                                 index=[now, now + timedelta(hours=1)],
                                 columns=["column_one", "column_two",
                                          "column_three"])
        points = [
            {
                "points": [
                    ["1", 1, 1.0, 0],
                    ["2", 2, 2.0, 3600]
                ],
                "name": "foo",
                "columns": ["column_one", "column_two", "column_three", "time"]
            }
        ]

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/db/db/series")

            cli = DataFrameClient(database='db')
            cli.write_points({"foo": dataframe})

            self.assertListEqual(json.loads(m.last_request.body), points)

    def test_write_points_from_dataframe_with_float_nan(self):
        """Test write points from dataframe with NaN float."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        dataframe = pd.DataFrame(data=[[1, float("NaN"), 1.0], [2, 2, 2.0]],
                                 index=[now, now + timedelta(hours=1)],
                                 columns=["column_one", "column_two",
                                          "column_three"])
        points = [
            {
                "points": [
                    [1, None, 1.0, 0],
                    [2, 2, 2.0, 3600]
                ],
                "name": "foo",
                "columns": ["column_one", "column_two", "column_three", "time"]
            }
        ]

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/db/db/series")

            cli = DataFrameClient(database='db')
            cli.write_points({"foo": dataframe})

            self.assertListEqual(json.loads(m.last_request.body), points)

    def test_write_points_from_dataframe_in_batches(self):
        """Test write points from dataframe in batches."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        dataframe = pd.DataFrame(data=[["1", 1, 1.0], ["2", 2, 2.0]],
                                 index=[now, now + timedelta(hours=1)],
                                 columns=["column_one", "column_two",
                                          "column_three"])
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/db/db/series")

            cli = DataFrameClient(database='db')
            self.assertTrue(cli.write_points({"foo": dataframe}, batch_size=1))

    def test_write_points_from_dataframe_with_numeric_column_names(self):
        """Test write points from dataframe with numeric columns."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        # df with numeric column names
        dataframe = pd.DataFrame(data=[["1", 1, 1.0], ["2", 2, 2.0]],
                                 index=[now, now + timedelta(hours=1)])
        points = [
            {
                "points": [
                    ["1", 1, 1.0, 0],
                    ["2", 2, 2.0, 3600]
                ],
                "name": "foo",
                "columns": ['0', '1', '2', "time"]
            }
        ]

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/db/db/series")

            cli = DataFrameClient(database='db')
            cli.write_points({"foo": dataframe})

            self.assertListEqual(json.loads(m.last_request.body), points)

    def test_write_points_from_dataframe_with_period_index(self):
        """Test write points from dataframe with period index."""
        dataframe = pd.DataFrame(data=[["1", 1, 1.0], ["2", 2, 2.0]],
                                 index=[pd.Period('1970-01-01'),
                                        pd.Period('1970-01-02')],
                                 columns=["column_one", "column_two",
                                          "column_three"])
        points = [
            {
                "points": [
                    ["1", 1, 1.0, 0],
                    ["2", 2, 2.0, 86400]
                ],
                "name": "foo",
                "columns": ["column_one", "column_two", "column_three", "time"]
            }
        ]

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/db/db/series")

            cli = DataFrameClient(database='db')
            cli.write_points({"foo": dataframe})

            self.assertListEqual(json.loads(m.last_request.body), points)

    def test_write_points_from_dataframe_with_time_precision(self):
        """Test write points from dataframe with time precision."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        dataframe = pd.DataFrame(data=[["1", 1, 1.0], ["2", 2, 2.0]],
                                 index=[now, now + timedelta(hours=1)],
                                 columns=["column_one", "column_two",
                                          "column_three"])
        points = [
            {
                "points": [
                    ["1", 1, 1.0, 0],
                    ["2", 2, 2.0, 3600]
                ],
                "name": "foo",
                "columns": ["column_one", "column_two", "column_three", "time"]
            }
        ]

        points_ms = copy.deepcopy(points)
        points_ms[0]["points"][1][-1] = 3600 * 1000

        points_us = copy.deepcopy(points)
        points_us[0]["points"][1][-1] = 3600 * 1000000

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/db/db/series")

            cli = DataFrameClient(database='db')

            cli.write_points({"foo": dataframe}, time_precision='s')
            self.assertListEqual(json.loads(m.last_request.body), points)

            cli.write_points({"foo": dataframe}, time_precision='m')
            self.assertListEqual(json.loads(m.last_request.body), points_ms)

            cli.write_points({"foo": dataframe}, time_precision='u')
            self.assertListEqual(json.loads(m.last_request.body), points_us)

    @raises(TypeError)
    def test_write_points_from_dataframe_fails_without_time_index(self):
        """Test write points from dataframe that fails without time index."""
        dataframe = pd.DataFrame(data=[["1", 1, 1.0], ["2", 2, 2.0]],
                                 columns=["column_one", "column_two",
                                          "column_three"])

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/db/db/series")

            cli = DataFrameClient(database='db')
            cli.write_points({"foo": dataframe})

    @raises(TypeError)
    def test_write_points_from_dataframe_fails_with_series(self):
        """Test failed write points from dataframe with series."""
        now = pd.Timestamp('1970-01-01 00:00+00:00')
        dataframe = pd.Series(data=[1.0, 2.0],
                              index=[now, now + timedelta(hours=1)])

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/db/db/series")

            cli = DataFrameClient(database='db')
            cli.write_points({"foo": dataframe})

    def test_query_into_dataframe(self):
        """Test query into a dataframe."""
        data = [
            {
                "name": "foo",
                "columns": ["time", "sequence_number", "column_one"],
                "points": [
                    [3600, 16, 2], [3600, 15, 1],
                    [0, 14, 2], [0, 13, 1]
                ]
            }
        ]
        # dataframe sorted ascending by time first, then sequence_number
        dataframe = pd.DataFrame(data=[[13, 1], [14, 2], [15, 1], [16, 2]],
                                 index=pd.to_datetime([0, 0,
                                                      3600, 3600],
                                                      unit='s', utc=True),
                                 columns=['sequence_number', 'column_one'])
        with _mocked_session('get', 200, data):
            cli = DataFrameClient('host', 8086, 'username', 'password', 'db')
            result = cli.query('select column_one from foo;')
            assert_frame_equal(dataframe, result)

    def test_query_multiple_time_series(self):
        """Test query for multiple time series."""
        data = [
            {
                "name": "series1",
                "columns": ["time", "mean", "min", "max", "stddev"],
                "points": [[0, 323048, 323048, 323048, 0]]
            },
            {
                "name": "series2",
                "columns": ["time", "mean", "min", "max", "stddev"],
                "points": [[0, -2.8233, -2.8503, -2.7832, 0.0173]]
            },
            {
                "name": "series3",
                "columns": ["time", "mean", "min", "max", "stddev"],
                "points": [[0, -0.01220, -0.01220, -0.01220, 0]]
            }
        ]
        dataframes = {
            'series1': pd.DataFrame(data=[[323048, 323048, 323048, 0]],
                                    index=pd.to_datetime([0], unit='s',
                                                         utc=True),
                                    columns=['mean', 'min', 'max', 'stddev']),
            'series2': pd.DataFrame(data=[[-2.8233, -2.8503, -2.7832, 0.0173]],
                                    index=pd.to_datetime([0], unit='s',
                                                         utc=True),
                                    columns=['mean', 'min', 'max', 'stddev']),
            'series3': pd.DataFrame(data=[[-0.01220, -0.01220, -0.01220, 0]],
                                    index=pd.to_datetime([0], unit='s',
                                                         utc=True),
                                    columns=['mean', 'min', 'max', 'stddev'])
        }
        with _mocked_session('get', 200, data):
            cli = DataFrameClient('host', 8086, 'username', 'password', 'db')
            result = cli.query("""select mean(value), min(value), max(value),
                stddev(value) from series1, series2, series3""")
            self.assertEqual(dataframes.keys(), result.keys())
            for key in dataframes.keys():
                assert_frame_equal(dataframes[key], result[key])

    def test_query_with_empty_result(self):
        """Test query with empty results."""
        with _mocked_session('get', 200, []):
            cli = DataFrameClient('host', 8086, 'username', 'password', 'db')
            result = cli.query('select column_one from foo;')
            self.assertEqual(result, [])

    def test_list_series(self):
        """Test list of series for dataframe object."""
        response = [
            {
                'columns': ['time', 'name'],
                'name': 'list_series_result',
                'points': [[0, 'seriesA'], [0, 'seriesB']]
            }
        ]
        with _mocked_session('get', 200, response):
            cli = DataFrameClient('host', 8086, 'username', 'password', 'db')
            series_list = cli.get_list_series()
            self.assertEqual(series_list, ['seriesA', 'seriesB'])

    def test_datetime_to_epoch(self):
        """Test convert datetime to epoch."""
        timestamp = pd.Timestamp('2013-01-01 00:00:00.000+00:00')
        cli = DataFrameClient('host', 8086, 'username', 'password', 'db')

        self.assertEqual(
            cli._datetime_to_epoch(timestamp),
            1356998400.0
        )
        self.assertEqual(
            cli._datetime_to_epoch(timestamp, time_precision='s'),
            1356998400.0
        )
        self.assertEqual(
            cli._datetime_to_epoch(timestamp, time_precision='m'),
            1356998400000.0
        )
        self.assertEqual(
            cli._datetime_to_epoch(timestamp, time_precision='ms'),
            1356998400000.0
        )
        self.assertEqual(
            cli._datetime_to_epoch(timestamp, time_precision='u'),
            1356998400000000.0
        )
