# -*- coding: utf-8 -*-
"""Define set of helper functions for the dataframe."""

import unittest
import warnings

import mock
from influxdb.influxdb08 import SeriesHelper, InfluxDBClient
from requests.exceptions import ConnectionError


class TestSeriesHelper(unittest.TestCase):
    """Define the SeriesHelper for test."""

    @classmethod
    def setUpClass(cls):
        """Set up an instance of the TestSerisHelper object."""
        super(TestSeriesHelper, cls).setUpClass()

        TestSeriesHelper.client = InfluxDBClient(
            'host',
            8086,
            'username',
            'password',
            'database'
        )

        class MySeriesHelper(SeriesHelper):
            """Define a subset SeriesHelper instance."""

            class Meta:
                """Define metadata for the TestSeriesHelper object."""

                client = TestSeriesHelper.client
                series_name = 'events.stats.{server_name}'
                fields = ['time', 'server_name']
                bulk_size = 5
                autocommit = True

        TestSeriesHelper.MySeriesHelper = MySeriesHelper

    def test_auto_commit(self):
        """Test that write_points called after the right number of events."""
        class AutoCommitTest(SeriesHelper):
            """Define an instance of SeriesHelper for AutoCommit test."""

            class Meta:
                """Define metadata AutoCommitTest object."""

                series_name = 'events.stats.{server_name}'
                fields = ['time', 'server_name']
                bulk_size = 5
                client = InfluxDBClient()
                autocommit = True

        fake_write_points = mock.MagicMock()
        AutoCommitTest(server_name='us.east-1', time=159)
        AutoCommitTest._client.write_points = fake_write_points
        AutoCommitTest(server_name='us.east-1', time=158)
        AutoCommitTest(server_name='us.east-1', time=157)
        AutoCommitTest(server_name='us.east-1', time=156)
        self.assertFalse(fake_write_points.called)
        AutoCommitTest(server_name='us.east-1', time=3443)
        self.assertTrue(fake_write_points.called)

    def testSingleSeriesName(self):
        """Test JSON conversion when there is only one series name."""
        TestSeriesHelper.MySeriesHelper(server_name='us.east-1', time=159)
        TestSeriesHelper.MySeriesHelper(server_name='us.east-1', time=158)
        TestSeriesHelper.MySeriesHelper(server_name='us.east-1', time=157)
        TestSeriesHelper.MySeriesHelper(server_name='us.east-1', time=156)
        expectation = [{'points': [[159, 'us.east-1'],
                                   [158, 'us.east-1'],
                                   [157, 'us.east-1'],
                                   [156, 'us.east-1']],
                        'name': 'events.stats.us.east-1',
                        'columns': ['time', 'server_name']}]

        rcvd = TestSeriesHelper.MySeriesHelper._json_body_()
        self.assertTrue(all([el in expectation for el in rcvd]) and
                        all([el in rcvd for el in expectation]),
                        'Invalid JSON body of time series returned from '
                        '_json_body_ for one series name: {0}.'.format(rcvd))
        TestSeriesHelper.MySeriesHelper._reset_()
        self.assertEqual(
            TestSeriesHelper.MySeriesHelper._json_body_(),
            [],
            'Resetting helper did not empty datapoints.')

    def testSeveralSeriesNames(self):
        """Test JSON conversion when there is only one series name."""
        TestSeriesHelper.MySeriesHelper(server_name='us.east-1', time=159)
        TestSeriesHelper.MySeriesHelper(server_name='fr.paris-10', time=158)
        TestSeriesHelper.MySeriesHelper(server_name='lu.lux', time=157)
        TestSeriesHelper.MySeriesHelper(server_name='uk.london', time=156)
        expectation = [{'points': [[157, 'lu.lux']],
                        'name': 'events.stats.lu.lux',
                        'columns': ['time', 'server_name']},
                       {'points': [[156, 'uk.london']],
                        'name': 'events.stats.uk.london',
                        'columns': ['time', 'server_name']},
                       {'points': [[158, 'fr.paris-10']],
                        'name': 'events.stats.fr.paris-10',
                        'columns': ['time', 'server_name']},
                       {'points': [[159, 'us.east-1']],
                        'name': 'events.stats.us.east-1',
                        'columns': ['time', 'server_name']}]

        rcvd = TestSeriesHelper.MySeriesHelper._json_body_()
        self.assertTrue(all([el in expectation for el in rcvd]) and
                        all([el in rcvd for el in expectation]),
                        'Invalid JSON body of time series returned from '
                        '_json_body_ for several series names: {0}.'
                        .format(rcvd))
        TestSeriesHelper.MySeriesHelper._reset_()
        self.assertEqual(
            TestSeriesHelper.MySeriesHelper._json_body_(),
            [],
            'Resetting helper did not empty datapoints.')

    def testInvalidHelpers(self):
        """Test errors in invalid helpers."""
        class MissingMeta(SeriesHelper):
            """Define SeriesHelper object for MissingMeta test."""

            pass

        class MissingClient(SeriesHelper):
            """Define SeriesHelper object for MissingClient test."""

            class Meta:
                """Define metadata for MissingClient object."""

                series_name = 'events.stats.{server_name}'
                fields = ['time', 'server_name']
                autocommit = True

        class MissingSeriesName(SeriesHelper):
            """Define SeriesHelper object for MissingSeries test."""

            class Meta:
                """Define metadata for MissingSeriesName object."""

                fields = ['time', 'server_name']

        class MissingFields(SeriesHelper):
            """Define SeriesHelper for MissingFields test."""

            class Meta:
                """Define metadata for MissingFields object."""

                series_name = 'events.stats.{server_name}'

        for cls in [MissingMeta, MissingClient, MissingFields,
                    MissingSeriesName]:
            self.assertRaises(
                AttributeError, cls, **{'time': 159,
                                        'server_name': 'us.east-1'})

    def testWarnBulkSizeZero(self):
        """Test warning for an invalid bulk size."""
        class WarnBulkSizeZero(SeriesHelper):
            """Define SeriesHelper for WarnBulkSizeZero test."""

            class Meta:
                """Define metadata for WarnBulkSizeZero object."""

                client = TestSeriesHelper.client
                series_name = 'events.stats.{server_name}'
                fields = ['time', 'server_name']
                bulk_size = 0
                autocommit = True

        with warnings.catch_warnings(record=True) as rec_warnings:
            warnings.simplefilter("always")
            # Server defined in the client is invalid, we're testing
            # the warning only.
            with self.assertRaises(ConnectionError):
                WarnBulkSizeZero(time=159, server_name='us.east-1')

        self.assertGreaterEqual(
            len(rec_warnings), 1,
            '{0} call should have generated one warning.'
            'Actual generated warnings: {1}'.format(
                WarnBulkSizeZero, '\n'.join(map(str, rec_warnings))))

        expected_msg = (
            'Definition of bulk_size in WarnBulkSizeZero forced to 1, '
            'was less than 1.')

        self.assertIn(expected_msg, list(w.message.args[0]
                                         for w in rec_warnings),
                      'Warning message did not contain "forced to 1".')

    def testWarnBulkSizeNoEffect(self):
        """Test warning for a set bulk size but autocommit False."""
        class WarnBulkSizeNoEffect(SeriesHelper):
            """Define SeriesHelper for WarnBulkSizeNoEffect object."""

            class Meta:
                """Define metadata for WarnBulkSizeNoEffect object."""

                series_name = 'events.stats.{server_name}'
                fields = ['time', 'server_name']
                bulk_size = 5
                autocommit = False

        with warnings.catch_warnings(record=True) as rec_warnings:
            warnings.simplefilter("always")
            WarnBulkSizeNoEffect(time=159, server_name='us.east-1')

        self.assertGreaterEqual(
            len(rec_warnings), 1,
            '{0} call should have generated one warning.'
            'Actual generated warnings: {1}'.format(
                WarnBulkSizeNoEffect, '\n'.join(map(str, rec_warnings))))

        expected_msg = (
            'Definition of bulk_size in WarnBulkSizeNoEffect has no affect '
            'because autocommit is false.')

        self.assertIn(expected_msg, list(w.message.args[0]
                                         for w in rec_warnings),
                      'Warning message did not contain the expected_msg.')


if __name__ == '__main__':
    unittest.main()
