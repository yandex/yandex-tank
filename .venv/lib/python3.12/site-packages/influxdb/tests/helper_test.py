# -*- coding: utf-8 -*-
"""Set of series helper functions for test."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from datetime import datetime, timedelta

import unittest
import warnings

import mock
from influxdb import SeriesHelper, InfluxDBClient
from requests.exceptions import ConnectionError


class TestSeriesHelper(unittest.TestCase):
    """Define the SeriesHelper test object."""

    @classmethod
    def setUpClass(cls):
        """Set up the TestSeriesHelper object."""
        super(TestSeriesHelper, cls).setUpClass()

        TestSeriesHelper.client = InfluxDBClient(
            'host',
            8086,
            'username',
            'password',
            'database'
        )

        class MySeriesHelper(SeriesHelper):
            """Define a SeriesHelper object."""

            class Meta:
                """Define metadata for the SeriesHelper object."""

                client = TestSeriesHelper.client
                series_name = 'events.stats.{server_name}'
                fields = ['some_stat']
                tags = ['server_name', 'other_tag']
                bulk_size = 5
                autocommit = True

        TestSeriesHelper.MySeriesHelper = MySeriesHelper

    def setUp(self):
        """Check that MySeriesHelper has empty datapoints."""
        super(TestSeriesHelper, self).setUp()
        self.assertEqual(
            TestSeriesHelper.MySeriesHelper._json_body_(),
            [],
            'Resetting helper in teardown did not empty datapoints.')

    def tearDown(self):
        """Deconstruct the TestSeriesHelper object."""
        super(TestSeriesHelper, self).tearDown()
        TestSeriesHelper.MySeriesHelper._reset_()
        self.assertEqual(
            TestSeriesHelper.MySeriesHelper._json_body_(),
            [],
            'Resetting helper did not empty datapoints.')

    def test_auto_commit(self):
        """Test write_points called after valid number of events."""
        class AutoCommitTest(SeriesHelper):
            """Define a SeriesHelper instance to test autocommit."""

            class Meta:
                """Define metadata for AutoCommitTest."""

                series_name = 'events.stats.{server_name}'
                fields = ['some_stat']
                tags = ['server_name', 'other_tag']
                bulk_size = 5
                client = InfluxDBClient()
                autocommit = True

        fake_write_points = mock.MagicMock()
        AutoCommitTest(server_name='us.east-1', some_stat=159, other_tag='gg')
        AutoCommitTest._client.write_points = fake_write_points
        AutoCommitTest(server_name='us.east-1', some_stat=158, other_tag='gg')
        AutoCommitTest(server_name='us.east-1', some_stat=157, other_tag='gg')
        AutoCommitTest(server_name='us.east-1', some_stat=156, other_tag='gg')
        self.assertFalse(fake_write_points.called)
        AutoCommitTest(server_name='us.east-1', some_stat=3443, other_tag='gg')
        self.assertTrue(fake_write_points.called)

    @mock.patch('influxdb.helper.SeriesHelper._current_timestamp')
    def testSingleSeriesName(self, current_timestamp):
        """Test JSON conversion when there is only one series name."""
        current_timestamp.return_value = current_date = datetime.today()
        TestSeriesHelper.MySeriesHelper(
            server_name='us.east-1', other_tag='ello', some_stat=159)
        TestSeriesHelper.MySeriesHelper(
            server_name='us.east-1', other_tag='ello', some_stat=158)
        TestSeriesHelper.MySeriesHelper(
            server_name='us.east-1', other_tag='ello', some_stat=157)
        TestSeriesHelper.MySeriesHelper(
            server_name='us.east-1', other_tag='ello', some_stat=156)
        expectation = [
            {
                "measurement": "events.stats.us.east-1",
                "tags": {
                    "other_tag": "ello",
                    "server_name": "us.east-1"
                },
                "fields": {
                    "some_stat": 159
                },
                "time": current_date,
            },
            {
                "measurement": "events.stats.us.east-1",
                "tags": {
                    "other_tag": "ello",
                    "server_name": "us.east-1"
                },
                "fields": {
                    "some_stat": 158
                },
                "time": current_date,
            },
            {
                "measurement": "events.stats.us.east-1",
                "tags": {
                    "other_tag": "ello",
                    "server_name": "us.east-1"
                },
                "fields": {
                    "some_stat": 157
                },
                "time": current_date,
            },
            {
                "measurement": "events.stats.us.east-1",
                "tags": {
                    "other_tag": "ello",
                    "server_name": "us.east-1"
                },
                "fields": {
                    "some_stat": 156
                },
                "time": current_date,
            }
        ]

        rcvd = TestSeriesHelper.MySeriesHelper._json_body_()
        self.assertTrue(all([el in expectation for el in rcvd]) and
                        all([el in rcvd for el in expectation]),
                        'Invalid JSON body of time series returned from '
                        '_json_body_ for one series name: {0}.'.format(rcvd))

    @mock.patch('influxdb.helper.SeriesHelper._current_timestamp')
    def testSeveralSeriesNames(self, current_timestamp):
        """Test JSON conversion when there are multiple series names."""
        current_timestamp.return_value = current_date = datetime.today()
        TestSeriesHelper.MySeriesHelper(
            server_name='us.east-1', some_stat=159, other_tag='ello')
        TestSeriesHelper.MySeriesHelper(
            server_name='fr.paris-10', some_stat=158, other_tag='ello')
        TestSeriesHelper.MySeriesHelper(
            server_name='lu.lux', some_stat=157, other_tag='ello')
        TestSeriesHelper.MySeriesHelper(
            server_name='uk.london', some_stat=156, other_tag='ello')
        expectation = [
            {
                'fields': {
                    'some_stat': 157
                },
                'measurement': 'events.stats.lu.lux',
                'tags': {
                    'other_tag': 'ello',
                    'server_name': 'lu.lux'
                },
                "time": current_date,
            },
            {
                'fields': {
                    'some_stat': 156
                },
                'measurement': 'events.stats.uk.london',
                'tags': {
                    'other_tag': 'ello',
                    'server_name': 'uk.london'
                },
                "time": current_date,
            },
            {
                'fields': {
                    'some_stat': 158
                },
                'measurement': 'events.stats.fr.paris-10',
                'tags': {
                    'other_tag': 'ello',
                    'server_name': 'fr.paris-10'
                },
                "time": current_date,
            },
            {
                'fields': {
                    'some_stat': 159
                },
                'measurement': 'events.stats.us.east-1',
                'tags': {
                    'other_tag': 'ello',
                    'server_name': 'us.east-1'
                },
                "time": current_date,
            }
        ]

        rcvd = TestSeriesHelper.MySeriesHelper._json_body_()
        self.assertTrue(all([el in expectation for el in rcvd]) and
                        all([el in rcvd for el in expectation]),
                        'Invalid JSON body of time series returned from '
                        '_json_body_ for several series names: {0}.'
                        .format(rcvd))

    @mock.patch('influxdb.helper.SeriesHelper._current_timestamp')
    def testSeriesWithoutTimeField(self, current_timestamp):
        """Test that time is optional on a series without a time field."""
        current_date = datetime.today()
        yesterday = current_date - timedelta(days=1)
        current_timestamp.return_value = yesterday
        TestSeriesHelper.MySeriesHelper(
            server_name='us.east-1', other_tag='ello',
            some_stat=159, time=current_date
        )
        TestSeriesHelper.MySeriesHelper(
            server_name='us.east-1', other_tag='ello',
            some_stat=158,
        )
        point1, point2 = TestSeriesHelper.MySeriesHelper._json_body_()
        self.assertTrue('time' in point1 and 'time' in point2)
        self.assertEqual(point1['time'], current_date)
        self.assertEqual(point2['time'], yesterday)

    def testSeriesWithoutAllTags(self):
        """Test that creating a data point without a tag throws an error."""
        class MyTimeFieldSeriesHelper(SeriesHelper):

            class Meta:
                client = TestSeriesHelper.client
                series_name = 'events.stats.{server_name}'
                fields = ['some_stat', 'time']
                tags = ['server_name', 'other_tag']
                bulk_size = 5
                autocommit = True

        self.assertRaises(NameError, MyTimeFieldSeriesHelper,
                          **{"server_name": 'us.east-1',
                             "some_stat": 158})

    @mock.patch('influxdb.helper.SeriesHelper._current_timestamp')
    def testSeriesWithTimeField(self, current_timestamp):
        """Test that time is optional on a series with a time field."""
        current_date = datetime.today()
        yesterday = current_date - timedelta(days=1)
        current_timestamp.return_value = yesterday

        class MyTimeFieldSeriesHelper(SeriesHelper):

            class Meta:
                client = TestSeriesHelper.client
                series_name = 'events.stats.{server_name}'
                fields = ['some_stat', 'time']
                tags = ['server_name', 'other_tag']
                bulk_size = 5
                autocommit = True

        MyTimeFieldSeriesHelper(
            server_name='us.east-1', other_tag='ello',
            some_stat=159, time=current_date
        )
        MyTimeFieldSeriesHelper(
            server_name='us.east-1', other_tag='ello',
            some_stat=158,
        )
        point1, point2 = MyTimeFieldSeriesHelper._json_body_()
        self.assertTrue('time' in point1 and 'time' in point2)
        self.assertEqual(point1['time'], current_date)
        self.assertEqual(point2['time'], yesterday)

    def testInvalidHelpers(self):
        """Test errors in invalid helpers."""
        class MissingMeta(SeriesHelper):
            """Define instance of SeriesHelper for missing meta."""

            pass

        class MissingClient(SeriesHelper):
            """Define SeriesHelper for missing client data."""

            class Meta:
                """Define metadat for MissingClient."""

                series_name = 'events.stats.{server_name}'
                fields = ['time', 'server_name']
                autocommit = True

        class MissingSeriesName(SeriesHelper):
            """Define instance of SeriesHelper for missing series."""

            class Meta:
                """Define metadata for MissingSeriesName."""

                fields = ['time', 'server_name']

        class MissingFields(SeriesHelper):
            """Define instance of SeriesHelper for missing fields."""

            class Meta:
                """Define metadata for MissingFields."""

                series_name = 'events.stats.{server_name}'

        class InvalidTimePrecision(SeriesHelper):
            """Define instance of SeriesHelper for invalid time precision."""

            class Meta:
                """Define metadata for InvalidTimePrecision."""

                series_name = 'events.stats.{server_name}'
                time_precision = "ks"
                fields = ['time', 'server_name']
                autocommit = True

        for cls in [MissingMeta, MissingClient, MissingFields,
                    MissingSeriesName, InvalidTimePrecision]:
            self.assertRaises(
                AttributeError, cls, **{'time': 159,
                                        'server_name': 'us.east-1'})

    @unittest.skip("Fails on py32")
    def testWarnBulkSizeZero(self):
        """Test warning for an invalid bulk size."""
        class WarnBulkSizeZero(SeriesHelper):

            class Meta:
                client = TestSeriesHelper.client
                series_name = 'events.stats.{server_name}'
                fields = ['time', 'server_name']
                tags = []
                bulk_size = 0
                autocommit = True

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            try:
                WarnBulkSizeZero(time=159, server_name='us.east-1')
            except ConnectionError:
                # Server defined in the client is invalid, we're testing
                # the warning only.
                pass
            self.assertEqual(len(w), 1,
                             '{0} call should have generated one warning.'
                             .format(WarnBulkSizeZero))
            self.assertIn('forced to 1', str(w[-1].message),
                          'Warning message did not contain "forced to 1".')

    def testWarnBulkSizeNoEffect(self):
        """Test warning for a set bulk size but autocommit False."""
        class WarnBulkSizeNoEffect(SeriesHelper):
            """Define SeriesHelper for warning on bulk size."""

            class Meta:
                """Define metadat for WarnBulkSizeNoEffect."""

                series_name = 'events.stats.{server_name}'
                fields = ['time', 'server_name']
                bulk_size = 5
                tags = []
                autocommit = False

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            WarnBulkSizeNoEffect(time=159, server_name='us.east-1')
            self.assertEqual(len(w), 1,
                             '{0} call should have generated one warning.'
                             .format(WarnBulkSizeNoEffect))
            self.assertIn('has no affect', str(w[-1].message),
                          'Warning message did not contain "has not affect".')

    def testSeriesWithRetentionPolicy(self):
        """Test that the data is saved with the specified retention policy."""
        my_policy = 'my_policy'

        class RetentionPolicySeriesHelper(SeriesHelper):

            class Meta:
                client = InfluxDBClient()
                series_name = 'events.stats.{server_name}'
                fields = ['some_stat', 'time']
                tags = ['server_name', 'other_tag']
                bulk_size = 2
                autocommit = True
                retention_policy = my_policy

        fake_write_points = mock.MagicMock()
        RetentionPolicySeriesHelper(
            server_name='us.east-1', some_stat=159, other_tag='gg')
        RetentionPolicySeriesHelper._client.write_points = fake_write_points
        RetentionPolicySeriesHelper(
            server_name='us.east-1', some_stat=158, other_tag='aa')

        kall = fake_write_points.call_args
        args, kwargs = kall
        self.assertTrue('retention_policy' in kwargs)
        self.assertEqual(kwargs['retention_policy'], my_policy)

    def testSeriesWithoutRetentionPolicy(self):
        """Test that the data is saved without any retention policy."""
        class NoRetentionPolicySeriesHelper(SeriesHelper):

            class Meta:
                client = InfluxDBClient()
                series_name = 'events.stats.{server_name}'
                fields = ['some_stat', 'time']
                tags = ['server_name', 'other_tag']
                bulk_size = 2
                autocommit = True

        fake_write_points = mock.MagicMock()
        NoRetentionPolicySeriesHelper(
            server_name='us.east-1', some_stat=159, other_tag='gg')
        NoRetentionPolicySeriesHelper._client.write_points = fake_write_points
        NoRetentionPolicySeriesHelper(
            server_name='us.east-1', some_stat=158, other_tag='aa')

        kall = fake_write_points.call_args
        args, kwargs = kall
        self.assertTrue('retention_policy' in kwargs)
        self.assertEqual(kwargs['retention_policy'], None)
